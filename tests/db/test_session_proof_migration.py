"""An older populated database must not invent second-factor proof on upgrade."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

import bedrock_server_manager.db.database as database_module


def test_populated_session_proof_upgrade_and_downgrade(tmp_path):
    config = Config(str(Path(database_module.__file__).parent / "alembic.ini"))
    config.set_main_option("skip_logging_config", "true")
    engine = create_engine(f"sqlite:///{tmp_path / 'proof.db'}")
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "g83c712e49a0")
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
            command.upgrade(config, "head")
            row = connection.execute(
                text(
                    "SELECT authentication_method, factor_verified FROM login_sessions"
                )
            ).one()
            assert row == ("unknown", False)
            command.downgrade(config, "g83c712e49a0")
            assert "factor_verified" not in {
                item["name"]
                for item in inspect(connection).get_columns("login_sessions")
            }
            assert (
                connection.execute(text("SELECT name FROM login_sessions")).scalar_one()
                == "old login"
            )
            command.upgrade(config, "head")
            assert (
                connection.execute(
                    text("SELECT factor_verified FROM login_sessions")
                ).scalar_one()
                == 0
            )
    finally:
        engine.dispose()
