from bedrock_server_manager.db.models import Server, User
from bedrock_server_manager.utils.database import (
    backup_database,
    get_backup_metadata,
    restore_database,
)


def test_backup_and_restore_database(app_context, tmp_path):
    # Setup initial data
    with app_context.db.session_manager() as session:
        user = User(username="testuser", hashed_password="pw", role="admin")
        server = Server(server_name="testserver", installed_version="1.0.0")
        session.add(user)
        session.add(server)
        session.commit()

    backup_file = tmp_path / "backup.json"
    backup_database(app_context.db, str(backup_file))

    assert backup_file.exists()
    metadata = get_backup_metadata(str(backup_file))
    assert isinstance(metadata, dict)

    # Modify data
    with app_context.db.session_manager() as session:
        session.query(User).delete()
        session.query(Server).delete()
        session.commit()

    # Verify modification
    with app_context.db.session_manager() as session:
        assert session.query(User).count() == 0

    import json

    with open(backup_file, "r") as f:
        backup_data = json.load(f)

    restore_database(app_context.db, backup_data)

    # Verify restore
    with app_context.db.session_manager() as session:
        assert session.query(User).count() == 1
        assert session.query(Server).count() == 1
