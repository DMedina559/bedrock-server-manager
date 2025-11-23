# src/bedrock_server_manager/db/database.py
"""
Database abstraction layer for Bedrock Server Manager.

This module provides the :class:`~.Database` class, which handles the connection
to the database (SQLite, PostgreSQL, etc.) using SQLAlchemy. It manages session
creation and lifecycle.
"""

import warnings
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.orm import declarative_base

from ..config.const import package_name
from ..config import bcm_config

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

    def __init__(self, db_url: str = None):
        """
        Initializes the Database instance.

        Args:
            db_url (str, optional): The database connection URL. If not provided,
                it will be loaded from the application configuration.
        """
        self.db_url = db_url
        self.engine = None
        self.SessionLocal = None
        self._tables_created = False

    def get_database_url(self):
        """
        Gets the database url from config.

        Returns:
            str: The database URL.

        Raises:
            RuntimeError: If 'db_url' is missing from the configuration.
        """
        if self.db_url:
            return self.db_url

        config = bcm_config.load_config()
        db_url = config.get("db_url")

        if not db_url:
            raise RuntimeError(
                f"Database URL not found in config. Please set 'db_url' in {package_name} config."
            )

        return db_url

    def initialize(self):
        """
        Initializes the database engine and session.

        Creates the SQLAlchemy engine and the session factory. This method is idempotent.
        """
        if self.engine:
            return

        db_url = self.get_database_url()

        connect_args = {}
        if db_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        self.engine = create_engine(
            db_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        self._tables_created = False

    def _ensure_tables_created(self):
        """
        Ensures that the database tables are created.
        This is done lazily on the first session request.
        """
        if not self._tables_created:
            if not self.engine:
                self.initialize()
            Base.metadata.create_all(bind=self.engine)
            self._tables_created = True

    @contextmanager
    def session_manager(self) -> Session:
        """
        Context manager for database sessions.

        Yields:
            Session: A database session.
        """
        if not self.SessionLocal:
            self.initialize()
        self._ensure_tables_created()
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def close(self):
        """Closes the database connection engine."""
        if self.engine:
            self.engine.dispose()
