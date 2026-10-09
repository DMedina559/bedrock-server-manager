from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from bedrock_server_manager.db.database import Database


async def test_database_initialization_with_url():
    database = Database(db_url="sqlite+aiosqlite:///:memory:")
    database.initialize()
    try:
        assert isinstance(database.engine, AsyncEngine)
        assert database.SessionLocal is not None
        assert not database._tables_created
    finally:
        await database.shutdown()


async def test_session_manager_uses_migrated_schema(db):
    async with db.session_manager() as session:
        assert isinstance(session, AsyncSession)
        version = (
            await session.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one()
        assert version
        tables = await session.run_sync(
            lambda sync: inspect(sync.bind).get_table_names()
        )
        assert {"users", "servers", "alembic_version"}.issubset(tables)


async def test_real_migrations_are_idempotent_and_persist_on_reopen(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'migration.db'}"
    versions = []
    for _ in range(2):
        database = Database(url)
        database.initialize()
        try:
            async with database.session_manager() as session:
                versions.append(
                    (
                        await session.execute(
                            text("SELECT version_num FROM alembic_version")
                        )
                    ).scalar_one()
                )
            await database._ensure_tables_created()
        finally:
            await database.shutdown()
    assert versions[0] == versions[1]
