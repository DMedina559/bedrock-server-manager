# src/bedrock_server_manager/db/database.py
"""
Database abstraction layer for Bedrock Server Manager.

This module provides the :class:`~.Database` class, which handles the connection
to the database (SQLite, PostgreSQL, etc.) using SQLAlchemy. It manages session
creation and lifecycle.
"""

import asyncio
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class Database:
    """
    Manages database connections and sessions.

    Attributes:
        db_url (str): The database connection URL.
        engine (Engine): The SQLAlchemy engine.
        SessionLocal (sessionmaker): The session factory.
        _tables_created (bool): Flag indicating if tables have been created.
    """

    def __init__(self, db_url: str):
        """
        Initializes the Database instance.

        Args:
            db_url (str, optional): The database connection URL. If not provided,
                it will be loaded from the application configuration.
        """
        self.db_url = db_url
        self.engine = None
        self.SessionLocal = None
        self.async_engine = None
        self.AsyncSessionLocal = None
        self._tables_created = False
        self._async_tables_created = False

    def _get_async_db_url(self) -> str:
        """Converts the standard database URL into an async-compatible URL."""
        if self.db_url.startswith("sqlite://"):
            return self.db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        if self.db_url.startswith("postgresql://"):
            return self.db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if self.db_url.startswith("mysql://") or self.db_url.startswith("mariadb://"):
            return self.db_url.replace("://", "+aiomysql://", 1)
        return self.db_url

    def initialize(self):
        """
        Initializes the database engine and session.

        Creates the SQLAlchemy engine and the session factory. This method is idempotent.
        """
        if self.engine:
            return

        db_url = self.db_url

        connect_args = {}
        if db_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        self.engine = create_engine(
            db_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self.SessionLocal = sessionmaker(autoflush=False, bind=self.engine)
        self._tables_created = False

    def async_initialize(self):
        """
        Initializes the async database engine and async session.

        Creates the SQLAlchemy async engine and the async session factory.
        """
        if self.async_engine:
            return

        async_db_url = self._get_async_db_url()

        connect_args = {}
        # aiosqlite doesn't use check_same_thread like standard sqlite does,
        # but if we needed specific aiosqlite connection args, they'd go here.

        self.async_engine = create_async_engine(
            async_db_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self.AsyncSessionLocal = async_sessionmaker(
            bind=self.async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        self._async_tables_created = False

    def _ensure_tables_created(self):
        """
        Ensures that the database tables are created.
        This is done lazily on the first session request using Alembic.
        """
        if not self._tables_created:
            if not self.engine:
                self.initialize()

            from sqlalchemy import inspect

            inspector = inspect(self.engine)
            # If there are no tables (or just very few, but we can check if 'users' exists)
            # we consider it a brand new database and run migrations automatically.
            if not inspector.has_table("users"):
                import logging
                from importlib.resources import files

                from alembic import command
                from alembic.config import Config

                # Suppress alembic output during normal startup
                logging.getLogger("alembic").setLevel(logging.WARNING)

                alembic_ini_path = files("bedrock_server_manager").joinpath(
                    "db/alembic.ini"
                )
                alembic_cfg = Config(str(alembic_ini_path))
                alembic_cfg.set_main_option("skip_logging_config", "true")
                alembic_cfg.set_main_option("sqlalchemy.url", self.db_url)

                with self.engine.begin() as connection:
                    alembic_cfg.attributes["connection"] = connection
                    command.upgrade(alembic_cfg, "head")

            self._tables_created = True

    async def _async_ensure_tables_created(self):
        """
        Ensures that the database tables are created asynchronously.
        Since Alembic migrations are primarily synchronous, we wrap the
        synchronous table creation logic here using `asyncio.to_thread`.
        """
        if not self._async_tables_created:
            if not self.async_engine:
                self.async_initialize()

            await asyncio.to_thread(self._ensure_tables_created)
            self._async_tables_created = True

    @contextmanager
    def session_manager(self):
        """
        Context manager for database sessions.

        Yields:
            Session: A database session.
        """
        if not self.SessionLocal:
            self.initialize()
        self._ensure_tables_created()
        assert self.SessionLocal is not None
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    @asynccontextmanager
    async def async_session_manager(self):
        """
        Async context manager for database sessions.

        Yields:
            AsyncSession: An async database session.
        """
        if not self.AsyncSessionLocal:
            self.async_initialize()
        await self._async_ensure_tables_created()
        assert self.AsyncSessionLocal is not None
        async with self.AsyncSessionLocal() as db:
            yield db

    def close(self):
        """Closes the database connection engine."""
        if self.engine:
            self.engine.dispose()

    async def shutdown(self):
        """Gracefully closes the database connection asynchronously."""

        if self.async_engine:
            await self.async_engine.dispose()
        await asyncio.to_thread(self.close)
