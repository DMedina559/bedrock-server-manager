import os
from unittest.mock import patch, MagicMock

import pytest

from bedrock_server_manager.db import database


@patch("bedrock_server_manager.db.database.get_settings_instance")
@patch("bedrock_server_manager.db.database.bcm_config.load_config")
def test_get_database_url_priority(mock_load_config, mock_get_settings, tmp_path):
    """Test that get_database_url respects the priority: config > env > default."""
    # 1. Test config file priority
    mock_load_config.return_value = {"db_url": "config_db_url"}
    assert database.get_database_url() == "config_db_url"
    mock_load_config.return_value = {}

    # 2. Test default path
    mock_settings = MagicMock()
    mock_settings.app_data_dir = str(tmp_path)
    mock_get_settings.return_value = mock_settings
    expected_path = os.path.join(str(tmp_path), ".config", "bedrock-server-manager.db")
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
