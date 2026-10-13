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


async def test_unreadable_migration_head_does_not_mark_schema_ready(
    tmp_path, monkeypatch
):
    import pytest
    from alembic.script import ScriptDirectory

    from bedrock_server_manager.error import ConfigurationError

    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'head.db'}")
    database.initialize()
    try:
        async with database.session_manager():
            pass
        database._tables_created = False

        def missing(*args, **kwargs):
            raise FileNotFoundError("migration resources missing")

        with monkeypatch.context() as fault:
            fault.setattr(ScriptDirectory, "from_config", missing)
            with pytest.raises(ConfigurationError):
                async with database.session_manager():
                    pass
            assert not database._tables_created
        async with database.session_manager():
            pass
        assert database._tables_created
    finally:
        await database.shutdown()


def test_migration_urls_select_declared_sync_drivers():
    from sqlalchemy.engine import make_url

    cases = {
        "sqlite:///test.db": "sqlite:///test.db",
        "postgresql://localhost/test": "postgresql+psycopg://localhost/test",
        "postgresql+asyncpg://localhost/test": "postgresql+psycopg://localhost/test",
        "mysql://localhost/test": "mysql+pymysql://localhost/test",
        "mariadb+aiomysql://localhost/test": "mariadb+pymysql://localhost/test",
    }
    for source, expected in cases.items():
        actual = Database(source)._get_sync_db_url()
        assert actual == expected
        assert not make_url(actual).get_dialect().is_async
