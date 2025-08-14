import os
from unittest.mock import patch, MagicMock

import pytest

from bedrock_server_manager.db import database


@patch("bedrock_server_manager.db.database.bcm_config.load_config")
def test_get_database_url(mock_load_config):
    """Test that get_database_url returns the URL from bcm_config."""
    mock_load_config.return_value = {"db_url": "test_db_url"}
    assert database.get_database_url() == "test_db_url"

    mock_load_config.return_value = {}
    with pytest.raises(RuntimeError):
        database.get_database_url()


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
