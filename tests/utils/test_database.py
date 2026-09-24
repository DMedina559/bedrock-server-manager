import json

from sqlalchemy import delete, func, select

from bedrock_server_manager.db.models import Server, User
from bedrock_server_manager.utils.database import (
    backup_database,
    get_backup_metadata,
    get_current_db_revision,
    restore_database,
)


async def test_backup_and_restore_database(app_context, tmp_path):
    """Test backup_database creates a valid json copy and restore_database restores it accurately."""
    # Prepare initial data
    async with app_context.db.session_manager() as session:
        user = User(username="db_test_user", hashed_password="pw", role="admin")
        server = Server(server_name="db_test_server", installed_version="1.0.0")
        session.add(user)
        session.add(server)
        await session.commit()

    backup_file = tmp_path / "test_backup.json"

    # Run backup
    await backup_database(app_context.db, str(backup_file))
    assert backup_file.exists()

    # Check metadata
    metadata = await get_backup_metadata(str(backup_file))
    assert isinstance(metadata, dict)
    assert "alembic_version" in metadata or len(metadata) == 0

    # Delete data
    async with app_context.db.session_manager() as session:
        await session.execute(delete(User))
        await session.execute(delete(Server))
        await session.commit()

        u_count = (
            await session.execute(select(func.count()).select_from(User))
        ).scalar()
        s_count = (
            await session.execute(select(func.count()).select_from(Server))
        ).scalar()
        assert u_count == 0
        assert s_count == 0

    # Restore data
    with open(backup_file, "r") as f:
        backup_data = json.load(f)

    await restore_database(app_context.db, backup_data)

    # Verify restore
    async with app_context.db.session_manager() as session:
        u_count = (
            await session.execute(select(func.count()).select_from(User))
        ).scalar()
        s_count = (
            await session.execute(select(func.count()).select_from(Server))
        ).scalar()
        assert u_count == 1
        assert s_count == 1

        res = await session.execute(select(User))
        restored_user = res.scalars().first()
        assert restored_user.username == "db_test_user"


async def test_restore_database_missing_models(app_context):
    """Test restore_database ignores missing or unknown models from the payload mapping."""
    backup_data = {
        "User": [
            {"username": "missing_model_user", "hashed_password": "pw", "role": "admin"}
        ],
        "NonExistentModel": [{"foo": "bar"}],
    }

    await restore_database(app_context.db, backup_data)

    async with app_context.db.session_manager() as session:
        res = await session.execute(select(User))
        users = res.scalars().all()
        assert len(users) == 1
        assert users[0].username == "missing_model_user"


async def test_get_current_db_revision_no_engine():
    """Test get_current_db_revision returns None smoothly if no valid engine is passed."""
    res = await get_current_db_revision(None)
    assert res is None
