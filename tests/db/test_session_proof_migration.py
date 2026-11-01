"""Session rows default to unverified factor proof unless explicitly recorded."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

import bedrock_server_manager.db.database as database_module


def test_session_proof_defaults_and_downgrade(tmp_path):
    config = Config(str(Path(database_module.__file__).parent / "alembic.ini"))
    config.set_main_option("skip_logging_config", "true")
    engine = create_engine(f"sqlite:///{tmp_path / 'proof.db'}")
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "f72c401a908b")
            command.upgrade(config, "head")
            connection.execute(
                text(
                    "INSERT INTO login_sessions (id, owner_id, name, user_agent, ip_address, created_at, last_seen_at, expires_at, verified_at) VALUES (:id, :owner, :name, :agent, :ip, 1, 1, 9999999999, 1)"
                ),
                {
                    "id": "a" * 32,
                    "owner": "b" * 32,
                    "name": "old login",
                    "agent": "test",
                    "ip": "127.0.0.1",
                },
            )
            row = connection.execute(
                text(
                    "SELECT authentication_method, factor_verified FROM login_sessions"
                )
            ).one()
            assert row == ("unknown", 0)
            command.downgrade(config, "f72c401a908b")
            assert "login_sessions" not in set(inspect(connection).get_table_names())
            command.upgrade(config, "head")
            assert {
                "authentication_method",
                "factor_verified",
            } <= {
                item["name"]
                for item in inspect(connection).get_columns("login_sessions")
            }
    finally:
        engine.dispose()
