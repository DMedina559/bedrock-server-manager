"""Database abstraction layer for Bedrock Server Manager."""

import warnings
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

from ..config.const import package_name
from ..config import bcm_config

Base = declarative_base()


class Database:
    def __init__(self, db_url: str = None):
        self.db_url = db_url
        self.engine = None
        self.SessionLocal = None
        self._tables_created = False

    def get_database_url(self):
        """Gets the database url from config."""
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
        """Initializes the database engine and session."""
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
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
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
        """Context manager for database sessions."""
        if not self.SessionLocal:
            self.initialize()
        self._ensure_tables_created()
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()


# For backward compatibility
_db_instance = Database()

# These will be initialized by initialize_database()
engine = None
SessionLocal = None
_TABLES_CREATED = False


def get_database_url():
    """Gets the database url from config."""
    warnings.warn(
        "get_database_url is deprecated. Use Database.get_database_url() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _db_instance.get_database_url()


def initialize_database(db_url: str = None):
    """Initializes the database engine and session."""
    warnings.warn(
        "initialize_database is deprecated. Use Database.initialize() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    global engine, SessionLocal, _TABLES_CREATED
    _db_instance.db_url = db_url
    _db_instance.initialize()
    engine = _db_instance.engine
    SessionLocal = _db_instance.SessionLocal
    _TABLES_CREATED = _db_instance._tables_created


def get_db():
    """Yields a database session."""
    warnings.warn(
        "get_db is deprecated. Use Database.session_manager() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    with _db_instance.session_manager() as db:
        yield db


@contextmanager
def db_session_manager():
    """Context manager for database sessions."""
    warnings.warn(
        "db_session_manager is deprecated. Use Database.session_manager() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    with _db_instance.session_manager() as db:
        yield db
