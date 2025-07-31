import os
from unittest.mock import patch, MagicMock

import pytest

from bedrock_server_manager.db import database


def test_get_database_url_with_env_var(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@host:port/database")
    assert (
        database.get_database_url() == "postgresql://user:password@host:port/database"
    )


def test_get_database_url_without_env_var(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with patch("os.environ.get") as mock_get:
        mock_get.return_value = str(tmp_path)
        expected_path = os.path.join(str(tmp_path), ".config", "bsm.db")
        assert database.get_database_url() == f"sqlite:///{expected_path}"


def test_engine_creation(monkeypatch):
    with patch(
        "bedrock_server_manager.db.database.create_engine"
    ) as mock_create_engine:
        # Test sqlite
        database.initialize_database("sqlite:///test.db")
        mock_create_engine.assert_called_with(
            "sqlite:///test.db", connect_args={"check_same_thread": False}
        )

        # Test postgresql
        database.initialize_database("postgresql://user:password@host:5432/database")
        mock_create_engine.assert_called_with(
            "postgresql://user:password@host:5432/database", connect_args={}
        )


def test_get_db():
    # We are using a real in-memory sqlite database for this test,
    # so we can't easily mock the session.
    # Instead, we'll just check that get_db returns a session.
    from sqlalchemy.orm.session import Session

    db_generator = database.get_db()
    db = next(db_generator)
    assert isinstance(db, Session)
    db.close()
