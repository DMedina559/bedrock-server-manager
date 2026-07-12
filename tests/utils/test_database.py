import json

from bedrock_server_manager.db.models import Server, User
from bedrock_server_manager.utils.database import (
    backup_database,
    get_backup_metadata,
    get_current_db_revision,
    restore_database,
)


def test_backup_and_restore_database(app_context, tmp_path):
    """Test backup_database creates a valid json copy and restore_database restores it accurately."""
    # Prepare initial data
    with app_context.db.session_manager() as session:
        user = User(username="db_test_user", hashed_password="pw", role="admin")
        server = Server(server_name="db_test_server", installed_version="1.0.0")
        session.add(user)
        session.add(server)
        session.commit()

    backup_file = tmp_path / "test_backup.json"

    # Run backup
    backup_database(app_context.db, str(backup_file))
    assert backup_file.exists()

    # Check metadata
    metadata = get_backup_metadata(str(backup_file))
    assert isinstance(metadata, dict)
    assert "alembic_version" in metadata or len(metadata) == 0

    # Delete data
    with app_context.db.session_manager() as session:
        session.query(User).delete()
        session.query(Server).delete()
        session.commit()

        assert session.query(User).count() == 0
        assert session.query(Server).count() == 0

    # Restore data
    with open(backup_file, "r") as f:
        backup_data = json.load(f)

    restore_database(app_context.db, backup_data)

    # Verify restore
    with app_context.db.session_manager() as session:
        assert session.query(User).count() == 1
        assert session.query(Server).count() == 1

        restored_user = session.query(User).first()
        assert restored_user.username == "db_test_user"


def test_restore_database_missing_models(app_context):
    """Test restore_database ignores missing or unknown models from the payload mapping."""
    backup_data = {
        "User": [
            {"username": "missing_model_user", "hashed_password": "pw", "role": "admin"}
        ],
        "NonExistentModel": [{"foo": "bar"}],
    }

    restore_database(app_context.db, backup_data)

    with app_context.db.session_manager() as session:
        assert session.query(User).count() == 1
        restored_user = session.query(User).first()
        assert restored_user.username == "missing_model_user"


def test_get_current_db_revision_no_engine():
    """Test get_current_db_revision returns None smoothly if no valid engine is passed."""
    assert get_current_db_revision(None) is None
