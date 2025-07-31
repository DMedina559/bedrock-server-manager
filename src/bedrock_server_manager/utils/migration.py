import os
import json
import logging
from typing import Dict, Any
from ..db.database import db_session_manager
from ..db.models import Player, User, Server, Plugin
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

    # Back up the old file
    backup_path = f"{players_json_path}.bak"
    try:
        os.rename(players_json_path, backup_path)
        logger.info(f"Old players.json file backed up to {backup_path}")
    except OSError as e:
        logger.error(
            f"Failed to back up players.json to {backup_path}. "
            "Migration aborted. Please check file permissions."
        )
        return

    with db_session_manager() as db:
        try:
            for player_data in players:
                player = Player(
                    player_name=player_data.get("name"),
                    xuid=player_data.get("xuid"),
                )
                db.add(player)
            db.commit()
            logger.info(
                "Successfully migrated players from players.json to the database."
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to migrate players to the database: {e}")


def migrate_env_auth_to_db(env_name: str):
    """Migrates authentication from environment variables to the database."""
    from ..web.auth_utils import pwd_context

    username = os.environ.get(f"{env_name}_USERNAME")
    password = os.environ.get(f"{env_name}_PASSWORD")

    if not username or not password:
        return

    with db_session_manager() as db:
        try:
            # Check if the user already exists
            if db.query(User).filter_by(username=username).first():
                return

            # Check if the password from env is already a hash
            if pwd_context.identify(password):
                hashed_password = password
            else:
                hashed_password = pwd_context.hash(password)
            user = User(
                username=username, hashed_password=hashed_password, role="admin"
            )
            db.add(user)
            db.commit()
            logger.info(
                f"Successfully migrated user '{username}' from environment variables to the database."
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to migrate user '{username}' to the database: {e}")


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


def migrate_settings_v1_to_v2(
    old_config: dict, config_path: str, default_config: dict
) -> dict:
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


def migrate_env_token_to_db(env_name: str):
    """Migrates the JWT token from environment variables to the database."""
    from ..instances import get_settings_instance

    token = os.environ.get(f"{env_name}_TOKEN")

    if not token:
        return

    settings = get_settings_instance()
    settings.set("web.jwt_secret_key", token)
    logger.info(
        "Successfully migrated JWT token from environment variables to the database."
    )


def migrate_plugin_config_to_db(plugin_name: str, plugin_directory: str):
    """Migrates a plugin's configuration from a JSON file to the database."""
    config_file_path = os.path.join(plugin_directory, f"{plugin_name}.json")
    if not os.path.exists(config_file_path):
        return

    logger.info(f"Migrating config for plugin '{plugin_name}' from JSON to database.")

    # Back up the old file
    backup_path = f"{config_file_path}.bak"
    try:
        os.rename(config_file_path, backup_path)
        logger.info(f"Old plugin config file backed up to {backup_path}")
    except OSError as e:
        logger.error(
            f"Failed to back up plugin config file to {backup_path}. "
            "Migration aborted. Please check file permissions."
        )
        return

    try:
        with open(backup_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        with db_session_manager() as db:
            plugin_entry = Plugin(plugin_name=plugin_name, config=config_data)
            db.add(plugin_entry)
            db.commit()
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to migrate config for plugin '{plugin_name}': {e}")


def migrate_server_config_to_db(server_name: str, server_config_dir: str):
    """Migrates a server's configuration from a JSON file to the database."""
    config_file_path = os.path.join(server_config_dir, f"{server_name}_config.json")
    if not os.path.exists(config_file_path):
        return

    logger.info(f"Migrating config for server '{server_name}' from JSON to database.")

    # Back up the old file
    backup_path = f"{config_file_path}.bak"
    try:
        os.rename(config_file_path, backup_path)
        logger.info(f"Old server config file backed up to {backup_path}")
    except OSError as e:
        logger.error(
            f"Failed to back up server config file to {backup_path}. "
            "Migration aborted. Please check file permissions."
        )
        return

    try:
        with open(backup_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        with db_session_manager() as db:
            server_entry = Server(server_name=server_name, config=config_data)
            db.add(server_entry)
            db.commit()
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to migrate config for server '{server_name}': {e}")


def migrate_services_to_db():
    """Migrates systemd/Windows service status to the database."""
    from ..instances import get_server_instance, get_settings_instance
    import platform
    import subprocess

    settings = get_settings_instance()
    server_path = settings.get("paths.servers")
    if not server_path or not os.path.isdir(server_path):
        return

    for server_name in os.listdir(server_path):
        server = get_server_instance(server_name)
        if not server.is_installed():
            continue

        if platform.system() == "Linux":
            service_name = f"bedrock-{server_name}.service"
            service_path = os.path.join(
                os.path.expanduser("~"), ".config", "systemd", "user", service_name
            )
            if os.path.exists(service_path):
                try:
                    result = subprocess.run(
                        ["systemctl", "--user", "is-enabled", service_name],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0 and result.stdout.strip() == "enabled":
                        server.set_autostart(True)
                    else:
                        server.set_autostart(False)
                except FileNotFoundError:
                    pass
        elif platform.system() == "Windows":
            from ..core.system.windows import check_service_exists

            service_name = f"bedrock-{server_name}"
            try:
                if check_service_exists(service_name):
                    result = subprocess.run(
                        ["sc", "qc", service_name],
                        capture_output=True,
                        text=True,
                    )
                    if "AUTO_START" in result.stdout:
                        server.set_autostart(True)
                    else:
                        server.set_autostart(False)
            except Exception:
                pass
