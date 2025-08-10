"""Database abstraction layer for Bedrock Server Manager."""

from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

import os
from ..config.const import package_name, env_name
from ..config import bcm_config


# These will be initialized by initialize_database()
engine = None
SessionLocal = None
Base = declarative_base()
_TABLES_CREATED = False


def get_database_url():
    """Gets the database url from config, or returns a default."""
    # 1. Check config file
    config = bcm_config.load_config()
    db_url = config.get("db_url")
    if db_url:
        return db_url

    # 2. Fallback to default SQLite path
    # Use the settings instance to get the app_data_dir consistently
    config_dir = os.path.join(config.get("data_dir"), ".config")
    os.makedirs(config_dir, exist_ok=True)
    default_db_url = (
        f"sqlite:///{os.path.join(config_dir, 'bedrock-server-manager.db')}"
    )
    bcm_config.set_config_value("db_url", default_db_url)

    return default_db_url


def _ensure_tables_created():
    """
    Ensures that the database tables are created.
    This is done lazily on the first session request.
    """
    global _TABLES_CREATED
    if not _TABLES_CREATED:
        if not engine:
            initialize_database()
        Base.metadata.create_all(bind=engine)
        _TABLES_CREATED = True


def initialize_database(db_url: str = None):
    """Initializes the database engine and session."""
    global engine, SessionLocal, _TABLES_CREATED

    if db_url is None:
        db_url = get_database_url()

    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(db_url, connect_args=connect_args)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    _TABLES_CREATED = False


def get_db():
    """Yields a database session."""
    if not SessionLocal:
        initialize_database()
    _ensure_tables_created()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session_manager():
    """Context manager for database sessions."""
    if not SessionLocal:
        initialize_database()
    _ensure_tables_created()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
