# bedrock-server-manager/bedrock_server_manager/core/server/world.py
import os
import shutil
import zipfile
import logging
from bedrock_server_manager.core.error import (
    MissingArgumentError,
    DownloadExtractError,
    FileOperationError,
    BackupWorldError,
    DirectoryError,
)
from bedrock_server_manager.core.server import server

logger = logging.getLogger("bedrock_server_manager")


def extract_world(world_file, extract_dir):
    """Extracts a world from a .mcworld file to the specified directory.

    Args:
        world_file (str): Path to the .mcworld file.
        extract_dir (str): Directory to extract to.

    Raises:
        MissingArgumentError: If world_file or extract_dir is empty.
        FileOperationError: If world_file does not exist or cannot be extracted.
        DownloadExtractError: If the world_file is not a zip file
    """
    if not world_file:
        raise MissingArgumentError("extract_world: world_file is empty.")
    if not extract_dir:
        raise MissingArgumentError("extract_world: extract_dir is empty.")
    if not os.path.exists(world_file):
        logger.error(f"extract_world: world_file does not exist: {world_file}")
        raise FileOperationError(
            f"extract_world: world_file does not exist: {world_file}"
        )

    # Remove existing world folder content
    logger.info("Removing existing world folder...")
    try:
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
            logger.debug(f"Removed existing directory: {extract_dir}")
            os.makedirs(extract_dir, exist_ok=True)
            logger.debug(f"Created directory: {extract_dir}")
    except OSError as e:
        logger.error(f"Failed to remove existing world folder content: {e}")
        raise FileOperationError(
            f"Failed to remove existing world folder content: {e}"
        ) from e

    # Extract the new world
    logger.info(f"Extracting new world from {world_file} to {extract_dir}...")
    try:
        with zipfile.ZipFile(world_file, "r") as zip_ref:
            zip_ref.extractall(extract_dir)
        logger.info(f"World extracted to {extract_dir}")
    except zipfile.BadZipFile:
        logger.error(f"Failed to extract world from {world_file}: Invalid zip file.")
        raise DownloadExtractError(
            f"Failed to extract world from {world_file}: Invalid zip file."
        ) from None
    except OSError as e:
        logger.error(f"Failed to extract world from {world_file}: {e}")
        raise FileOperationError(
            f"Failed to extract world from {world_file}: {e}"
        ) from e


def export_world(world_path, backup_file):
    """Exports the world as a .mcworld file (ZIP archive).

    Args:
        world_path (str): Path to the world directory.
        backup_file (str): Path to save the backup file to.

    Raises:
        MissingArgumentError: If world_path or backup_file is empty.
        DirectoryError: If the world_path is not a directory.
        BackupWorldError: If backing up fails
        FileOperationError: If an unexpected error occurs.
    """
    if not world_path:
        raise MissingArgumentError("export_world: world_path is empty.")
    if not backup_file:
        raise MissingArgumentError("export_world: backup_file is empty.")
    if not os.path.isdir(world_path):
        logger.error(f"World directory '{world_path}' does not exist.")
        raise DirectoryError(f"World directory '{world_path}' does not exist.")

    logger.info(f"Backing up world folder '{world_path}' to {backup_file}...")
    try:
        # Ensure the directory for the backup file exists
        os.makedirs(os.path.dirname(backup_file), exist_ok=True)
        logger.debug(f"Created directory for backup file: {os.path.dirname(backup_file)}")

        shutil.make_archive(
            os.path.splitext(backup_file)[0],  # Base name (without extension)
            "zip",  # Format
            root_dir=world_path,  # What to archive
        )
        logger.debug(f"Created zip archive: {os.path.splitext(backup_file)[0] + '.zip'}")
        os.rename(os.path.splitext(backup_file)[0] + ".zip", backup_file)
        logger.info(f"World backup created: {backup_file}")
    except OSError as e:
        logger.error(f"Backup of world failed: {e}")
        raise BackupWorldError(f"Backup of world failed: {e}") from e
    except Exception as e:
        logger.error(f"An unexpected error: {e}")
        raise FileOperationError(f"An unexpected error: {e}") from e


def import_world(server_name, backup_file, base_dir):
    """Restores a world from a .mcworld file.

    Args:
        server_name (str): The name of the server.
        backup_file (str): Path to the .mcworld backup file.
        base_dir (str): The base directory for servers.

    Raises:
        FileOperationError: If the backup file doesn't exist or world name cannot be retrieved.
        # Other exceptions may be raised by extract_world
    """
    if not os.path.exists(backup_file):
        logger.error(f"restore_world: backup_file does not exist: {backup_file}")
        raise FileOperationError(
            f"restore_world: backup_file does not exist: {backup_file}"
        )

    server_dir = os.path.join(base_dir, server_name)
    logger.debug(f"Server directory: {server_dir}")
    try:
        world_name = server.get_world_name(server_name, base_dir)
        logger.info(f"World name: {world_name}")
    except Exception as e:  # Catch *any* error from get_world_name
        logger.error(f"Failed to get world name from server.properties: {e}")
        raise FileOperationError(
            f"Failed to get world name from server.properties: {e}"
        ) from e

    if world_name is None or not world_name:
        logger.error("Failed to get world name from server.properties (returned None or empty string).")
        raise FileOperationError(
            "Failed to get world name from server.properties (returned None or empty string)."
        )

    extract_dir = os.path.join(server_dir, "worlds", world_name)
    logger.info(f"Extracting world to: {extract_dir}")
    extract_world(backup_file, extract_dir)  # Let extract_world raise exceptions