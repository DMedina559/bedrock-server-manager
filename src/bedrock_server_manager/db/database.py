# src/bedrock_server_manager/db/database.py
"""
Database abstraction layer for Bedrock Server Manager.

This module provides the :class:`~.Database` class, which handles the connection
to the database (SQLite, PostgreSQL, etc.) using SQLAlchemy. It manages session
creation and lifecycle asynchronously.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from importlib.resources import files
from typing import AsyncGenerator

from alembic import command
from alembic.config import Config
from sqlalchemy import event, inspect
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Database:
    """
    Manages asynchronous database connections and sessions.

    Attributes:
        db_url (str): The database connection URL.
        engine (AsyncEngine): The SQLAlchemy async engine.
        SessionLocal (async_sessionmaker): The async session factory.
        _tables_created (bool): Flag indicating if tables have been created.
    """

    def __init__(self, db_url: str):
        """
        Initializes the Database instance.

        Args:
            db_url (str): The database connection URL.
        """
        self.db_url = db_url
        self.engine: AsyncEngine | None = None
        self.SessionLocal: async_sessionmaker[AsyncSession] | None = None
        self._tables_created = False

    def _get_db_url(self) -> str:
        """Converts the standard database URL into an async-compatible URL."""
        if self.db_url.startswith("sqlite://"):
            return self.db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        if self.db_url.startswith("postgresql://"):
            return self.db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if self.db_url.startswith("mysql://") or self.db_url.startswith("mariadb://"):
            return self.db_url.replace("://", "+aiomysql://", 1)
        return self.db_url

    def _get_sync_db_url(self) -> str:
        """Converts an async database URL back into a standard sync URL (for Alembic)."""
        url = self.db_url
        url = url.replace("sqlite+aiosqlite://", "sqlite://", 1)
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        url = url.replace("mysql+aiomysql://", "mysql://", 1)
        url = url.replace("mariadb+aiomysql://", "mariadb://", 1)
        return url

    def initialize(self) -> None:
        """
        Initializes the async database engine and session factory.
        This method is idempotent.
        """
        if self.engine:
            return

        db_url = self._get_db_url()

        connect_args = {}
        if db_url.startswith("sqlite"):
            connect_args["timeout"] = 20.0

        self.engine = create_async_engine(
            db_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            pool_recycle=3600,
        )

        if db_url.startswith("sqlite"):

            @event.listens_for(self.engine.sync_engine, "connect")
            def set_sqlite_pragma_async(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()

        self.SessionLocal = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        self._tables_created = False

    def _run_alembic_upgrade(self) -> None:
        """Runs synchronous Alembic migration command."""
        from sqlalchemy import create_engine

        sync_url = self._get_sync_db_url()
        logging.getLogger("alembic").setLevel(logging.WARNING)

        alembic_ini_path = files("bedrock_server_manager").joinpath("db/alembic.ini")
        alembic_cfg = Config(str(alembic_ini_path))
        alembic_cfg.set_main_option("skip_logging_config", "true")
        alembic_cfg.set_main_option("sqlalchemy.url", sync_url)

        sync_engine = create_engine(sync_url)
        with sync_engine.begin() as connection:
            alembic_cfg.attributes["connection"] = connection
            command.upgrade(alembic_cfg, "head")
        sync_engine.dispose()

    async def _ensure_tables_created(self) -> None:
        """
        Ensures that the database tables are created asynchronously.
        Checks for the 'users' table and runs migrations if needed.
        """
        if not self._tables_created:
            if not self.engine:
                self.initialize()

            assert self.engine is not None

            def has_users_table(conn):
                inspector = inspect(conn)
                return inspector.has_table("users")

            async with self.engine.connect() as conn:
                needs_creation = not await conn.run_sync(has_users_table)

            if needs_creation:
                await asyncio.to_thread(self._run_alembic_upgrade)

            self._tables_created = True

    @asynccontextmanager
    async def session_manager(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Async context manager for database sessions.

        Yields:
            AsyncSession: An async database session.
        """
        if not self.SessionLocal:
            self.initialize()
        await self._ensure_tables_created()
        assert self.SessionLocal is not None
        async with self.SessionLocal() as db:
            yield db

    def close(self) -> None:
        """Closes the database connection engine synchronously if possible."""
        if self.engine:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.engine.dispose())
            except RuntimeError:
                asyncio.run(self.engine.dispose())

    async def shutdown(self) -> None:
        """Gracefully closes the database connection engine asynchronously."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.SessionLocal = None
