import os
import json
import logging
from typing import Dict, Any
from ..db.database import SessionLocal
from ..db.models import Player, User
from ..error import ConfigurationError

logger = logging.getLogger(__name__)


def migrate_players_json_to_db(players_json_path: str):
    """Migrates players from players.json to the database."""
    try:
        with open(players_json_path, "r") as f:
            data = json.load(f)
            players = data.get("players", [])
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning(f"Could not read players.json from {players_json_path}")
        return

    db = SessionLocal()
    try:
        for player_data in players:
            player = Player(
                player_name=player_data.get("name"),
                xuid=player_data.get("xuid"),
            )
            db.add(player)
        db.commit()
        logger.info("Successfully migrated players from players.json to the database.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to migrate players to the database: {e}")
    finally:
        db.close()


def migrate_env_auth_to_db(env_name: str):
    """Migrates authentication from environment variables to the database."""
    from ..web.auth_utils import pwd_context

    username = os.environ.get(f"{env_name}_USERNAME")
    password = os.environ.get(f"{env_name}_PASSWORD")

    if not username or not password:
        return

    db = SessionLocal()
    try:
        # Check if the user already exists
        if db.query(User).filter_by(username=username).first():
            return

        hashed_password = pwd_context.hash(password)
        user = User(username=username, hashed_password=hashed_password, role="admin")
        db.add(user)
        db.commit()
        logger.info(f"Successfully migrated user '{username}' from environment variables to the database.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to migrate user '{username}' to the database: {e}")
    finally:
        db.close()


def migrate_server_config_v1_to_v2(
    old_config: Dict[str, Any], default_config: Dict[str, Any]
) -> Dict[str, Any]:
    """Migrates a flat v1 server configuration to the nested v2 format."""
    new_config = default_config.copy()
    new_config["server_info"]["installed_version"] = old_config.get(
        "installed_version", new_config["server_info"]["installed_version"]
    )
    new_config["settings"]["target_version"] = old_config.get(
        "target_version", new_config["settings"]["target_version"]
    )
    new_config["server_info"]["status"] = old_config.get(
        "status", new_config["server_info"]["status"]
    )
    autoupdate_val = old_config.get("autoupdate")
    if isinstance(autoupdate_val, str):
        new_config["settings"]["autoupdate"] = autoupdate_val.lower() == "true"
    elif isinstance(autoupdate_val, bool):
        new_config["settings"]["autoupdate"] = autoupdate_val
    known_v1_keys_handled = {
        "installed_version",
        "target_version",
        "status",
        "autoupdate",
        "config_schema_version",
    }
    for key, value in old_config.items():
        if key not in known_v1_keys_handled:
            new_config["custom"][key] = value
    new_config["config_schema_version"] = 2
    return new_config


def migrate_settings_v1_to_v2(old_config: dict, config_path: str, default_config: dict) -> dict:
    """Migrates a flat v1 configuration (no ``config_version`` key) to the nested v2 format.

    This method performs the following steps:

        1. Backs up the existing v1 configuration file to ``<config_file_name>.v1.bak``.
        2. Creates a new configuration structure based on :meth:`default_config`.
        3. Maps known keys from the old flat ``old_config`` dictionary to their
           new locations in the nested v2 structure.
        4. Sets ``config_version`` to ``CONFIG_SCHEMA_VERSION`` in the new structure.
        5. Writes the new v2 configuration to the primary configuration file.

    Args:
        old_config (dict): The loaded dictionary from the old, flat (v1)
            configuration file.
        config_path (str): The path to the configuration file.
        default_config (dict): The default configuration.

    Returns:
        dict: The migrated configuration.

    Raises:
        ConfigurationError: If backing up the old config file fails (e.g., due
            to file permissions).
    """
    logger.info(
        "Old configuration format (v1) detected. Migrating to new nested format (v2)..."
    )
    # 1. Back up the old file
    backup_path = f"{config_path}.v1.bak"
    try:
        os.rename(config_path, backup_path)
        logger.info(f"Old configuration file backed up to {backup_path}")
    except OSError as e:
        raise ConfigurationError(
            f"Failed to back up old config file to {backup_path}. "
            "Migration aborted. Please check file permissions."
        ) from e

    # 2. Create the new config by starting with defaults and overwriting with old values
    new_config = default_config
    key_map = {
        # Old Key: ("category", "new_key")
        "BASE_DIR": ("paths", "servers"),
        "CONTENT_DIR": ("paths", "content"),
        "DOWNLOAD_DIR": ("paths", "downloads"),
        "BACKUP_DIR": ("paths", "backups"),
        "PLUGIN_DIR": ("paths", "plugins"),
        "LOG_DIR": ("paths", "logs"),
        "BACKUP_KEEP": ("retention", "backups"),
        "DOWNLOAD_KEEP": ("retention", "downloads"),
        "LOGS_KEEP": ("retention", "logs"),
        "FILE_LOG_LEVEL": ("logging", "file_level"),
        "CLI_LOG_LEVEL": ("logging", "cli_level"),
        "WEB_PORT": ("web", "port"),
        "TOKEN_EXPIRES_WEEKS": ("web", "token_expires_weeks"),
    }
    for old_key, (category, new_key) in key_map.items():
        if old_key in old_config:
            new_config[category][new_key] = old_config[old_key]

    logger.info("Successfully migrated configuration to the new format.")
    return new_config
