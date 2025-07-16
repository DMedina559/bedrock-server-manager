"""Database abstraction layer for Bedrock Server Manager."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

import os
from ..config.const import package_name, env_name


def get_database_url():
    if "DATABASE_URL" in os.environ:
        return os.environ["DATABASE_URL"]

    env_var_name = f"{env_name}_DATA_DIR"
    data_dir = os.environ.get(env_var_name)
    if not data_dir:
        data_dir = os.path.join(os.path.expanduser("~"), f"{package_name}")

    config_dir = os.path.join(data_dir, ".config")
    os.makedirs(config_dir, exist_ok=True)

    return f"sqlite:///{os.path.join(config_dir, 'bsm.db')}"


DATABASE_URL = get_database_url()

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
