import os
from unittest.mock import patch, MagicMock

import pytest


def test_get_database_url_with_env_var(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@host:port/database")
    from bedrock_server_manager.db.database import get_database_url

    assert get_database_url() == "postgresql://user:password@host:port/database"


def test_get_database_url_without_env_var(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with patch("os.environ.get") as mock_get:
        mock_get.return_value = str(tmp_path)
        from bedrock_server_manager.db.database import get_database_url

        expected_path = os.path.join(str(tmp_path), ".config", "bsm.db")
        assert get_database_url() == f"sqlite:///{expected_path}"


def test_sqlite_engine_creation(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    with patch("sqlalchemy.create_engine") as mock_create_engine:
        from importlib import reload
        from bedrock_server_manager.db import database

        reload(database)
        mock_create_engine.assert_called_with(
            "sqlite:///test.db", connect_args={"check_same_thread": False}
        )


def test_postgresql_engine_creation(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@host:5432/database")
    with patch("sqlalchemy.create_engine") as mock_create_engine:
        from importlib import reload
        from bedrock_server_manager.db import database

        reload(database)
        mock_create_engine.assert_called_with(
            "postgresql://user:password@host:5432/database", connect_args={}
        )


def test_get_db():
    with patch("bedrock_server_manager.db.database.SessionLocal") as mock_session_local:
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        from bedrock_server_manager.db.database import get_db

        db_generator = get_db()
        db = next(db_generator)
        assert db == mock_db
        with pytest.raises(StopIteration):
            next(db_generator)
        mock_db.close.assert_called_once()
