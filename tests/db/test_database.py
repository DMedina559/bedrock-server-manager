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
        assert {
            "users",
            "servers",
            "alembic_version",
            "schedules",
            "schedule_runs",
        }.issubset(tables)


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


def test_access_migration_preserves_accounts_servers_and_identity(tmp_path):
    """Upgrade populated databases, reopen idempotently, and support downgrade."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine

    import bedrock_server_manager.db.database as database_module

    config = Config(str(Path(database_module.__file__).parent / "alembic.ini"))
    config.set_main_option("skip_logging_config", "true")
    engine = create_engine(f"sqlite:///{tmp_path / 'access-migration.db'}")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "f72c401a908b")
        connection.execute(
            text(
                "INSERT INTO users (username, hashed_password, role, is_active) VALUES ('existing', 'hash', 'user', 1)"
            )
        )
        connection.execute(
            text("INSERT INTO servers (server_name) VALUES ('existing-server')")
        )
        command.upgrade(config, "head")
        assert (
            connection.execute(text("SELECT auth_revision FROM users")).scalar_one()
            == 0
        )
        for table in (
            "login_sessions",
            "account_security",
            "auth_throttle",
            "auth_security_events",
        ):
            assert (
                connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
                == 0
            )
        identity = connection.execute(text("SELECT access_id FROM users")).scalar_one()
        assert len(identity) == 32
        assert (
            len(connection.execute(text("SELECT access_id FROM servers")).scalar_one())
            == 32
        )
        command.upgrade(config, "head")
        assert (
            connection.execute(text("SELECT access_id FROM users")).scalar_one()
            == identity
        )
        command.downgrade(config, "f72c401a908b")
        assert (
            connection.execute(text("SELECT username FROM users")).scalar_one()
            == "existing"
        )
        assert (
            connection.execute(text("SELECT server_name FROM servers")).scalar_one()
            == "existing-server"
        )
    engine.dispose()


async def test_sqlite_close_then_repeated_stop_does_not_leak_future_errors():
    """aiosqlite clears its connection before invoking the patched stop hook."""
    import asyncio
    import gc

    database = Database("sqlite+aiosqlite:///:memory:")
    database.initialize()
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    errors = []
    loop.set_exception_handler(lambda _loop, context: errors.append(context))
    try:
        async with database.engine.connect() as connection:
            adapted = await connection.get_raw_connection()
            raw = adapted.driver_connection
            await connection.execute(text("SELECT 1"))
        await raw.close()
        stopped = raw.stop()
        assert raw.stop() is stopped
        if stopped is not None:
            await stopped
        await database.shutdown()
        gc.collect()
        await asyncio.sleep(0)
        assert errors == []
    finally:
        await database.shutdown()
        loop.set_exception_handler(previous_handler)


def test_nonexpiring_token_migration_preserves_deadlines_and_downgrades_safely(
    tmp_path,
):
    import time
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine

    import bedrock_server_manager.db.database as database_module

    config = Config(str(Path(database_module.__file__).parent / "alembic.ini"))
    config.set_main_option("skip_logging_config", "true")
    engine = create_engine(f"sqlite:///{tmp_path / 'token-expiry.db'}")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "h94d823f50b1")
        insert = text(
            "INSERT INTO integration_tokens (id, owner_id, name, digest, permissions, created_at, expires_at) VALUES (:id, 'owner', 'test', 'hash', '[]', 1, :expiry)"
        )
        connection.execute(insert, {"id": "dated", "expiry": 2000000000})
        command.upgrade(config, "head")
        connection.execute(insert, {"id": "forever", "expiry": None})
        assert (
            connection.execute(
                text("SELECT expires_at FROM integration_tokens WHERE id='dated'")
            ).scalar_one()
            == 2000000000
        )
        before = int(time.time())
        command.downgrade(config, "h94d823f50b1")
        deadline = connection.execute(
            text("SELECT expires_at FROM integration_tokens WHERE id='forever'")
        ).scalar_one()
        assert before <= deadline <= int(time.time())
        assert (
            connection.execute(
                text("SELECT expires_at FROM integration_tokens WHERE id='dated'")
            ).scalar_one()
            == 2000000000
        )
        command.upgrade(config, "head")
    engine.dispose()


def test_registration_token_digest_migration_upgrades_plaintext_and_downgrades_safely(
    tmp_path,
):
    import hashlib
    import time
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine

    import bedrock_server_manager.db.database as database_module

    config = Config(str(Path(database_module.__file__).parent / "alembic.ini"))
    config.set_main_option("skip_logging_config", "true")
    engine = create_engine(f"sqlite:///{tmp_path / 'registration-migration.db'}")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        # 1. Upgrade to revision prior to digest storage
        command.upgrade(config, "i05e934a61c2")
        insert = text(
            "INSERT INTO registration_tokens (id, token, role, expires) VALUES (:id, :token, :role, :expires)"
        )
        raw_token = "legacy_secret_invite_123"
        expected_digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        connection.execute(
            insert,
            {
                "id": 1,
                "token": raw_token,
                "role": "user",
                "expires": int(time.time()) + 3600,
            },
        )

        # 2. Upgrade to head (j16f045b72d3)
        command.upgrade(config, "head")

        # 3. Verify column is token_digest and plaintext token is gone
        row = connection.execute(
            text("SELECT id, token_digest, role FROM registration_tokens WHERE id=1")
        ).fetchone()
        assert row is not None
        assert row[1] == expected_digest
        assert row[2] == "user"

        columns = [
            col["name"]
            for col in inspect(connection).get_columns("registration_tokens")
        ]
        assert "token_digest" in columns
        assert "token" not in columns

        # 4. Downgrade back to i05e934a61c2 and verify columns
        command.downgrade(config, "i05e934a61c2")
        columns_downgraded = [
            col["name"]
            for col in inspect(connection).get_columns("registration_tokens")
        ]
        assert "token" in columns_downgraded
        assert "token_digest" not in columns_downgraded

        # 5. Upgrade back to head
        command.upgrade(config, "head")
    engine.dispose()
