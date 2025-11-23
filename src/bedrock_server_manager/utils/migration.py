from __future__ import annotations
import os
import json
import logging
from ..web.auth_utils import get_password_hash
import platform
import subprocess
from typing import TYPE_CHECKING, Dict, Any, Optional

from ..db.models import Player, User, Server, Plugin
from ..error import ConfigurationError
from ..config import bcm_config
from ..config.const import env_name

if TYPE_CHECKING:
    from ..context import AppContext

logger = logging.getLogger(__name__)


def migrate_players_json_to_db(app_context: AppContext):
    """Migrates players from players.json to the database if the file exists."""
    players_json_path = os.path.join(app_context.settings.config_dir, "players.json")
    logger.info(f"Checking for players.json at {players_json_path}")
    if not os.path.exists(players_json_path):
        logger.info(
            f"players.json not found at {players_json_path}. Skipping migration."
        )
        return  # Source file doesn't exist, no migration needed.

    logger.info("Attempting to migrate players from players.json to the database...")

    try:
        with open(players_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            players = data.get("players", [])
            if not players:
                logger.info("players.json contains no players to migrate.")
                return
    except (json.JSONDecodeError, OSError) as e:
        logger.error(
            f"Could not read or parse players.json from {players_json_path}: {e}"
        )
        return

    # Back up the old file before database operations
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

    db = None
    try:
        with app_context.db.session_manager() as db:
            for player_data in players:
                # Check if player already exists to ensure idempotency
                if not db.query(Player).filter_by(xuid=player_data.get("xuid")).first():
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
        if db:
            db.rollback()
        logger.error(
            f"Failed to migrate players to the database: {e}. Restoring backup."
        )
        # Attempt to restore backup on DB failure
        try:
            os.rename(backup_path, players_json_path)
        except OSError as restore_e:
            logger.error(f"Failed to restore backup file: {restore_e}")


def _load_env_from_systemd_service(service_name: str) -> Dict[str, str]:
    """
    Loads environment variables from the EnvironmentFile of a systemd service.
    """
    if platform.system() != "Linux":
        return {}

    from ..core.system.linux import get_systemd_service_file_path

    try:
        service_path = get_systemd_service_file_path(service_name, system=True)
        if not os.path.exists(service_path):
            service_path = get_systemd_service_file_path(service_name, system=False)
            if not os.path.exists(service_path):
                return {}

        with open(service_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("EnvironmentFile="):
                    env_file_path = line.strip().split("=", 1)[1]
                    if env_file_path.startswith("-"):
                        env_file_path = env_file_path[1:]

                    if not os.path.isabs(env_file_path):
                        # Assuming the env file is relative to the service file's directory
                        # This is a common practice but might not cover all edge cases
                        env_file_path = os.path.join(
                            os.path.dirname(service_path), env_file_path
                        )

                    if os.path.exists(env_file_path):
                        env_vars = {}
                        with open(env_file_path, "r", encoding="utf-8") as env_file:
                            for env_line in env_file:
                                if "=" in env_line:
                                    key, value = env_line.strip().split("=", 1)
                                    env_vars[key] = value
                        return env_vars
    except Exception as e:
        logger.warning(
            f"Could not load environment from systemd service {service_name}: {e}"
        )

    return {}


def migrate_env_auth_to_db(app_context: AppContext):
    """Migrates authentication from environment variables to the database."""
    # Load environment from systemd service file if it exists
    systemd_env = _load_env_from_systemd_service("bedrock-server-manager-webui.service")

    env = os.environ.copy()
    env.update(systemd_env)

    username = env.get(f"{env_name}_USERNAME")
    password = env.get(f"{env_name}_PASSWORD")

    if not username or not password:
        return  # Environment variables not set, no migration needed.

    logger.info(
        f"Attempting to migrate user '{username}' from environment variables..."
    )

    db = None
    try:
        with app_context.db.session_manager() as db:
            # Check if the user already exists
            if db.query(User).filter_by(username=username).first():
                logger.info(
                    f"User '{username}' already exists in the database. Skipping migration."
                )
                return

            try:
                is_hashed = password.startswith(("$2a$", "$2b$", "$2y$"))
            except AttributeError:
                is_hashed = False

            if is_hashed:
                logger.info("Password is already hashed.")
                hashed_password = password
            else:
                logger.info("Password is not hashed. Hashing now.")
                hashed_password = get_password_hash(password)

            user = User(
                username=username, hashed_password=hashed_password, role="admin"
            )
            db.add(user)
            db.commit()
            logger.info(
                f"Successfully migrated user '{username}' from environment variables to the database."
            )
    except Exception as e:
        if db:
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
    """Migrates a flat v1 configuration (no ``config_version`` key) to the nested v2 format."""
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

    # 2. Create the new config
    new_config = default_config.copy()
    key_map = {
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


def migrate_env_token_to_db(app_context: AppContext):
    """Migrates the JWT token from an environment variable to the database."""
    token = os.environ.get(f"{env_name}_TOKEN")
    if not token:
        return

    logger.info(
        "Attempting to migrate JWT token from environment variable to database..."
    )
    try:
        settings = app_context.settings
        settings.set("web.jwt_secret_key", token)
        logger.info(
            "Successfully migrated JWT token from environment variable to the database."
        )
    except Exception as e:
        logger.error(f"Failed to migrate JWT token to the database: {e}")


def migrate_plugin_config_to_db(app_context: AppContext, config_dir: str):
    """
    Migrates plugin configurations from a single plugins.json file to the database,
    overwriting any existing default configurations.
    """
    config_file_path = os.path.join(config_dir, "plugins.json")
    logger.info(f"Checking for plugin config file at {config_file_path}")
    if not os.path.exists(config_file_path):
        logger.info(
            f"Plugin config file not found at {config_file_path}. Skipping migration."
        )
        return

    logger.info(
        "Migrating plugin configs from JSON to database, overwriting existing entries."
    )

    backup_path = f"{config_file_path}.bak"
    try:
        os.rename(config_file_path, backup_path)
        logger.info(f"Old plugin config file backed up to {backup_path}")
    except OSError as e:
        logger.error(
            f"Failed to back up plugin config file '{config_file_path}' to '{backup_path}'. "
            "Migration aborted. Please check file permissions."
        )
        return

    try:
        with open(backup_path, "r", encoding="utf-8") as f:
            all_plugins_config = json.load(f)

        with app_context.db.session_manager() as db:
            for plugin_name, config_data in all_plugins_config.items():
                # Find the existing plugin entry.
                plugin_entry = (
                    db.query(Plugin).filter_by(plugin_name=plugin_name).first()
                )

                if plugin_entry:
                    # Update the existing config with data from the JSON file.
                    plugin_entry.config = config_data
                    logger.info(f"Updating config for plugin '{plugin_name}'.")
                else:
                    # If no default entry exists, create a new one.
                    plugin_entry = Plugin(plugin_name=plugin_name, config=config_data)
                    db.add(plugin_entry)
                    logger.info(f"Creating new config for plugin '{plugin_name}'.")

            db.commit()
            logger.info("Successfully migrated all plugin configs from the JSON file.")

    except (json.JSONDecodeError, OSError, Exception) as e:
        logger.error(f"Failed to migrate plugin configs: {e}")
        try:
            os.rename(backup_path, config_file_path)
            logger.info(f"Restored plugin config backup for '{config_file_path}'.")
        except OSError as restore_e:
            logger.error(f"Failed to restore plugin config backup: {restore_e}")


def migrate_server_config_to_db(
    app_context: AppContext, server_name: str, server_config_dir: str
):
    """Migrates a server's configuration from a JSON file to the database."""
    config_dir = os.path.join(server_config_dir, server_name)
    config_file_path = os.path.join(config_dir, f"{server_name}_config.json")
    logger.info(f"Checking for server config file at {config_file_path}")
    if not os.path.exists(config_file_path):
        logger.info(
            f"Server config file not found at {config_file_path}. Skipping migration."
        )
        return

    logger.info(f"Migrating config for server '{server_name}' from JSON to database.")

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
        with app_context.db.session_manager() as db:
            # Check if config already exists
            if not db.query(Server).filter_by(server_name=server_name).first():
                server_entry = Server(server_name=server_name, config=config_data)
                db.add(server_entry)
                db.commit()
                logger.info(f"Successfully migrated config for server '{server_name}'.")
            else:
                logger.info(
                    f"Server '{server_name}' config already in database. Skipping."
                )
    except (json.JSONDecodeError, OSError, Exception) as e:
        logger.error(f"Failed to migrate config for server '{server_name}': {e}")
        try:
            os.rename(backup_path, config_file_path)
            logger.info(f"Restored server config backup for '{server_name}'.")
        except OSError as restore_e:
            logger.error(f"Failed to restore server config backup: {restore_e}")


def migrate_services_to_db(app_context: AppContext = None):
    """Migrates systemd/Windows service autostart status to the database."""

    logger.info("Checking for system services to migrate autostart status...")
    try:
        settings = app_context.settings
        server_path = settings.get("paths.servers")
        if not server_path or not os.path.isdir(server_path):
            logger.debug(
                "Server path not configured or not a directory. Skipping service migration."
            )
            return
    except Exception as e:
        logger.error(f"Could not retrieve settings for service migration: {e}")
        return

    for server_name in os.listdir(server_path):
        try:
            server = app_context.get_server(server_name)

            if not server.is_installed():
                continue

            autostart_enabled = False
            if platform.system() == "Linux":
                service_name = f"bedrock-{server_name}.service"
                result = subprocess.run(
                    ["systemctl", "--user", "is-enabled", service_name],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                autostart_enabled = (
                    result.returncode == 0 and result.stdout.strip() == "enabled"
                )
            elif platform.system() == "Windows":
                from ..core.system.windows import check_service_exists

                service_name = f"bedrock-{server_name}"
                if check_service_exists(service_name):
                    result = subprocess.run(
                        ["sc", "qc", service_name],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    autostart_enabled = "AUTO_START" in result.stdout

            server.set_autostart(autostart_enabled)
        except Exception as e:
            logger.error(
                f"Failed to migrate service status for server '{server_name}': {e}"
            )


def migrate_env_vars_to_config_file():
    """Migrates DATA_DIR from environment variables to the config file."""
    data_dir_env_var = f"{env_name}_DATA_DIR"
    data_dir_value = os.environ.get(data_dir_env_var)

    if not data_dir_value:
        return

    logger.info(f"Attempting to migrate {data_dir_env_var} to config file...")
    try:
        config = bcm_config.load_config()
        if "data_dir" not in config or config["data_dir"] != data_dir_value:
            config["data_dir"] = data_dir_value
            bcm_config.save_config(config)
            logger.info(
                f"Successfully migrated {data_dir_env_var} to config file. "
                "You can now remove this environment variable."
            )
    except Exception as e:
        logger.error(f"Failed to migrate environment variables to config file: {e}")


def migrate_json_configs_to_db(app_context: AppContext):
    """Migrates server and plugin JSON configs to the database."""
    # Migrate server configs
    server_base_dir = app_context.settings.get("paths.servers")
    config_dir = app_context.settings.config_dir
    if os.path.isdir(server_base_dir):
        for server_name in os.listdir(server_base_dir):
            server_dir = os.path.join(server_base_dir, server_name)
            if os.path.isdir(server_dir):
                try:

                    migrate_server_config_to_db(app_context, server_name, config_dir)
                except Exception as e:
                    logger.error(
                        f"Failed to migrate config for server '{server_name}': {e}"
                    )

    # Migrate plugin configs
    migrate_plugin_config_to_db(app_context, config_dir)


from ..db.models import Setting


def migrate_global_theme_to_admin_user(app_context: AppContext):
    """Migrates the global theme setting to the first admin user's preferences."""

    settings = app_context.settings

    logger.info("Checking for global theme setting to migrate to admin user...")
    try:
        global_theme = settings.get("web.theme")

        if not global_theme:
            logger.debug("No global theme set. Skipping migration.")
            return

        with app_context.db.session_manager() as db:
            admin_user = db.query(User).filter_by(role="admin").first()
            if admin_user:
                admin_user.theme = global_theme
                db.commit()
                logger.info(
                    f"Successfully migrated global theme '{global_theme}' to admin user '{admin_user.username}'."
                )
                # Remove the now-obsolete global theme setting
                settings.set("web.theme", None)
            else:
                logger.warning(
                    "Global theme found, but no admin user exists to migrate it to."
                )
    except Exception as e:
        logger.error(f"Failed to migrate global theme to admin user: {e}")


from ..config.settings import deep_merge


def migrate_json_settings_to_db(app_context: AppContext):
    """Migrates settings from a file-based bedrock_server_manager.json to the database."""
    config_path = os.path.join(
        app_context.settings.config_dir, "bedrock_server_manager.json"
    )

    if not os.path.exists(config_path):
        logger.debug(
            "bedrock_server_manager.json not found, no settings migration needed."
        )
        return

    logger.info(
        "Found old bedrock_server_manager.json, migrating settings to database..."
    )

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to read or parse old config file at {config_path}: {e}")
        return

    try:
        with app_context.db.session_manager() as db:
            current_db_settings = {}
            for s in db.query(Setting).all():
                current_db_settings[s.key] = s.value

            merged_config = deep_merge(config_data, current_db_settings)

            for key, value in merged_config.items():
                setting = db.query(Setting).filter_by(key=key).first()
                if setting:
                    if setting.value != value:
                        setting.value = value
                else:
                    setting = Setting(key=key, value=value)
                    db.add(setting)
            db.commit()

        app_context.settings.reload()

        backup_path = f"{config_path}.bak"
        if os.path.exists(backup_path):
            os.remove(backup_path)
        os.rename(config_path, backup_path)
        logger.info(f"Successfully migrated settings from {config_path} to database.")
        logger.info(f"Old config file has been backed up to {backup_path}.")

    except Exception as e:
        logger.error(
            f"An error occurred during settings migration from JSON to DB: {e}",
            exc_info=True,
        )
