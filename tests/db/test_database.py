from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.engine import Engine

from bedrock_server_manager.db.database import Database


def test_database_initialization_with_url():
    """Test Database initialization with an explicit URL."""
    db = Database(db_url="sqlite:///:memory:")
    db.initialize()

    assert db.engine is not None
    assert isinstance(db.engine, Engine)
    assert db.SessionLocal is not None
    assert not db._tables_created
    db.close()


def test_database_initialization_without_url(
    isolated_bcm_config, monkeypatch, tmp_path
):
    """Test Database initialization fetches URL from config."""
    db_path = tmp_path / "test_data" / "test.db"
    mock_config = {"db_url": f"sqlite:///{db_path}"}
    monkeypatch.setattr(
        "bedrock_server_manager.config.bcm_config.load_config", lambda: mock_config
    )

    db = Database()
    db.initialize()

    assert db.engine is not None
    assert db.SessionLocal is not None

    assert "test.db" in str(db.engine.url)
    db.close()


def test_database_missing_url_raises_error(isolated_bcm_config, monkeypatch):
    """Test get_database_url raises error if missing from config."""
    # Mock config to return empty
    monkeypatch.setattr(
        "bedrock_server_manager.config.bcm_config.load_config", lambda: {}
    )

    db = Database()
    with pytest.raises(RuntimeError, match="Database URL not found in config"):
        db.get_database_url()


def test_database_session_manager(db):
    """Test that session_manager yields a session and ensures tables are created."""
    assert not db._tables_created

    with db.session_manager() as session:
        assert session is not None
        assert db._tables_created  # Should trigger _ensure_tables_created

        # Test basic query to ensure tables exist
        from bedrock_server_manager.db.models import User

        users = session.query(User).all()
        assert isinstance(users, list)


def test_ensure_tables_created_idempotent(db, caplog):
    """Test _ensure_tables_created only runs migrations once."""
    assert not db._tables_created

    db._ensure_tables_created()
    assert db._tables_created

    # Run again, should not execute migrations
    db._ensure_tables_created()
    assert db._tables_created


@patch("alembic.command.upgrade")
def test_ensure_tables_created_runs_alembic(mock_upgrade, monkeypatch, tmp_path):
    """Test _ensure_tables_created triggers Alembic upgrade when tables are missing."""
    db_path = tmp_path / "isolated.db"
    db = Database(f"sqlite:///{db_path}")
    db.initialize()
    db._tables_created = False

    # Mock the resources to point to a valid file so alembic config doesn't fail
    import importlib.resources

    monkeypatch.setattr(
        importlib.resources,
        "files",
        MagicMock(
            return_value=MagicMock(
                joinpath=MagicMock(return_value=tmp_path / "alembic.ini")
            )
        ),
    )

    db._ensure_tables_created()

    mock_upgrade.assert_called_once()
    assert db._tables_created
    db.close()


def test_database_close(db):
    """Test database connection is disposed properly."""
    assert db.engine is not None
    db.close()
