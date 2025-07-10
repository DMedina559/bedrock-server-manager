# bedrock_server_manager/core/server/world_mixin.py
"""
Provides the :class:`.ServerWorldMixin` for the
:class:`~.core.bedrock_server.BedrockServer` class.

This mixin encapsulates logic related to managing a Bedrock server's world files.
Its responsibilities include:

    - Exporting an existing world directory to a ``.mcworld`` archive file.
    - Importing a world from a ``.mcworld`` archive, potentially replacing the
      server's active world.
    - Deleting the server's active world directory.
    - Locating and checking for the existence of the world icon (``world_icon.jpeg``).

Operations often involve determining the active world's name (via ``get_world_name()``,
expected from :class:`~.core.server.state_mixin.ServerStateMixin`) and interacting
with the filesystem within the server's ``worlds`` subdirectory.

.. warning::
    Some methods in this mixin, such as those for importing or deleting worlds,
    are **DESTRUCTIVE** and can lead to data loss if not used carefully.
"""
import os
import shutil
import zipfile
from typing import Optional, Any

# Local application imports.
from .base_server_mixin import BedrockServerBaseMixin
from ..system import base as system_base_utils
from ...error import (
    MissingArgumentError,
    ExtractError,
    FileOperationError,
    BackupRestoreError,
    AppFileNotFoundError,
    ConfigParseError,
)


class ServerWorldMixin(BedrockServerBaseMixin):
    """Provides methods for managing Bedrock server worlds.

    This mixin extends :class:`.BedrockServerBaseMixin` and adds functionalities
    for common world-related tasks such as exporting worlds to ``.mcworld``
    archives, importing worlds from these archives (potentially replacing the
    active world), and deleting the active world's directory. It also includes
    helpers for locating world-specific files like the world icon.

    It heavily relies on being able to determine the active world's name, which
    is typically provided by :meth:`~.core.server.state_mixin.ServerStateMixin.get_world_name`.
    Destructive operations like world import and deletion should be used with caution.

    Internal Properties:
        _worlds_base_dir_in_server (str): Path to the "worlds" subdirectory in the server installation.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes the ServerWorldMixin.

        Calls ``super().__init__(*args, **kwargs)`` to participate in cooperative
        multiple inheritance. It depends on attributes initialized by
        :class:`.BedrockServerBaseMixin` (e.g., `server_dir`, `logger`) and
        assumes methods like ``get_world_name()`` (from
        :class:`~.core.server.state_mixin.ServerStateMixin`) will be available on
        the composed :class:`~.core.bedrock_server.BedrockServer` object.

        Args:
            *args (Any): Variable length argument list passed to `super()`.
            **kwargs (Any): Arbitrary keyword arguments passed to `super()`.
        """
        super().__init__(*args, **kwargs)
        # Attributes from BaseMixin are available.
        # Relies on self.get_world_name() from StateMixin.

    @property
    def _worlds_base_dir_in_server(self) -> str:
        """str: The absolute path to the 'worlds' subdirectory within the server's
        installation directory (:attr:`~.BedrockServerBaseMixin.server_dir`).
        """
        return os.path.join(self.server_dir, "worlds")

    def _get_active_world_directory_path(self) -> str:
        """Determines the full path to the directory of the currently active world.

        This path is constructed by joining the base worlds directory
        (:attr:`._worlds_base_dir_in_server`) with the active world's name,
        which is obtained by calling ``self.get_world_name()``. This method
        is expected to be provided by :class:`~.core.server.state_mixin.ServerStateMixin`.

        Returns:
            str: The absolute path to the active world's directory.

        Raises:
            AttributeError: If the ``get_world_name`` method is not available on
                the instance (indicating a missing required mixin).
            AppFileNotFoundError: If ``server.properties`` (used by `get_world_name`)
                is not found.
            ConfigParseError: If ``level-name`` is missing from ``server.properties``
                or the file is malformed.
        """
        if not hasattr(self, "get_world_name"):
            # This indicates a programming error / incorrect mixin composition.
            self.logger.error(
                "Internal error: get_world_name method is missing from this Server instance."
            )
            raise AttributeError(
                "The 'get_world_name' method, typically from ServerStateMixin, is required but not found."
            )

        active_world_name: str = self.get_world_name()  # type: ignore
        if not active_world_name or not isinstance(active_world_name, str):
            # get_world_name should ideally raise if it can't determine, but double check.
            raise ConfigParseError(
                f"Active world name ('{active_world_name}') received from get_world_name() is invalid for server '{self.server_name}'."
            )
        return os.path.join(self._worlds_base_dir_in_server, active_world_name)

    def extract_mcworld_to_directory(
        self, mcworld_file_path: str, target_world_dir_name: str
    ) -> str:
        """Extracts a ``.mcworld`` archive file into a specified world directory name.

        The extraction target is a subdirectory named `target_world_dir_name`
        within the server's main "worlds" folder (see :attr:`._worlds_base_dir_in_server`).

        .. warning::
            If the `target_world_dir_name` directory already exists, **it will be
            deleted** before extraction to ensure a clean import.

        Args:
            mcworld_file_path (str): The absolute path to the ``.mcworld`` file
                to be extracted.
            target_world_dir_name (str): The desired name for the world directory
                that will be created inside the server's "worlds" folder to
                contain the extracted content.

        Returns:
            str: The absolute path to the directory where the world was extracted
            (e.g., ``<server_dir>/worlds/<target_world_dir_name>``).

        Raises:
            MissingArgumentError: If `mcworld_file_path` or `target_world_dir_name`
                are empty or not strings.
            AppFileNotFoundError: If the source `mcworld_file_path` does not exist
                or is not a file.
            FileOperationError: If creating the target directory structure or
                clearing a pre-existing target directory fails (e.g., due to
                permissions or other ``OSError``).
            ExtractError: If the ``.mcworld`` file is not a valid ZIP archive or
                if an error occurs during the extraction process itself.
        """
        if not isinstance(mcworld_file_path, str) or not mcworld_file_path:
            raise MissingArgumentError(
                "Path to the .mcworld file cannot be empty and must be a string."
            )
        if not target_world_dir_name:
            raise MissingArgumentError("Target world directory name cannot be empty.")

        full_target_extract_dir = os.path.join(
            self._worlds_base_dir_in_server, target_world_dir_name
        )
        mcworld_filename = os.path.basename(mcworld_file_path)

        self.logger.info(
            f"Server '{self.server_name}': Preparing to extract '{mcworld_filename}' into world directory '{target_world_dir_name}'."
        )

        if not os.path.isfile(mcworld_file_path):
            raise AppFileNotFoundError(mcworld_file_path, ".mcworld file")

        # Ensure a clean target directory by removing it if it exists.
        if os.path.exists(full_target_extract_dir):
            self.logger.warning(
                f"Target world directory '{full_target_extract_dir}' already exists. Removing its contents."
            )
            try:
                shutil.rmtree(full_target_extract_dir)
            except OSError as e:
                raise FileOperationError(
                    f"Failed to clear target world directory '{full_target_extract_dir}': {e}"
                ) from e

        # Recreate the empty target directory.
        try:
            os.makedirs(full_target_extract_dir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Failed to create target world directory '{full_target_extract_dir}': {e}"
            ) from e

        # Extract the world archive.
        self.logger.info(
            f"Server '{self.server_name}': Extracting '{mcworld_filename}'..."
        )
        try:
            with zipfile.ZipFile(mcworld_file_path, "r") as zip_ref:
                zip_ref.extractall(full_target_extract_dir)
            self.logger.info(
                f"Server '{self.server_name}': Successfully extracted world to '{full_target_extract_dir}'."
            )
            return full_target_extract_dir
        except zipfile.BadZipFile as e:
            # Clean up the partially created directory on failure.
            if os.path.exists(full_target_extract_dir):
                shutil.rmtree(full_target_extract_dir, ignore_errors=True)
            raise ExtractError(
                f"Invalid .mcworld file (not a valid zip): {mcworld_filename}"
            ) from e
        except OSError as e:
            raise FileOperationError(
                f"Error extracting world '{mcworld_filename}' for server '{self.server_name}': {e}"
            ) from e
        except Exception as e_unexp:
            raise FileOperationError(
                f"Unexpected error extracting world '{mcworld_filename}' for server '{self.server_name}': {e_unexp}"
            ) from e_unexp

    def export_world_directory_to_mcworld(
        self, world_dir_name: str, target_mcworld_file_path: str
    ) -> None:
        """Exports a specified world directory into a ``.mcworld`` archive file.

        This method takes the name of a world directory (located within the server's
        "worlds" folder), archives its entire contents into a ZIP file, and then
        renames this ZIP file to have a ``.mcworld`` extension, saving it to
        `target_mcworld_file_path`.

        The parent directory for `target_mcworld_file_path` will be created if
        it does not exist. If `target_mcworld_file_path` itself already exists,
        it will be overwritten. A temporary ``.zip`` file is created during the
        process and is cleaned up.

        Args:
            world_dir_name (str): The name of the world directory to export,
                relative to the server's "worlds" folder (e.g., "MyFavoriteWorld").
            target_mcworld_file_path (str): The absolute path where the resulting
                ``.mcworld`` archive file should be saved.

        Raises:
            MissingArgumentError: If `world_dir_name` or `target_mcworld_file_path`
                are empty or not strings.
            AppFileNotFoundError: If the source world directory
                (``<server_dir>/worlds/<world_dir_name>``) does not exist or is not a directory.
            FileOperationError: If creating the parent directory for the
                `target_mcworld_file_path` fails due to an ``OSError``.
            BackupRestoreError: If creating the ZIP archive (via ``shutil.make_archive``)
                or renaming it to ``.mcworld`` fails, or for other unexpected errors
                during the export process. This can wrap underlying ``OSError`` or
                other exceptions.
        """
        if not isinstance(world_dir_name, str) or not world_dir_name:
            raise MissingArgumentError(
                "Source world directory name cannot be empty and must be a string."
            )
        if not target_mcworld_file_path:
            raise MissingArgumentError("Target .mcworld file path cannot be empty.")

        full_source_world_dir = os.path.join(
            self._worlds_base_dir_in_server, world_dir_name
        )
        mcworld_filename = os.path.basename(target_mcworld_file_path)

        self.logger.info(
            f"Server '{self.server_name}': Exporting world '{world_dir_name}' to .mcworld file '{mcworld_filename}'."
        )

        if not os.path.isdir(full_source_world_dir):
            raise AppFileNotFoundError(full_source_world_dir, "Source world directory")

        # Ensure the parent directory for the exported file exists.
        target_parent_dir = os.path.dirname(target_mcworld_file_path)
        if target_parent_dir:
            try:
                os.makedirs(target_parent_dir, exist_ok=True)
            except OSError as e:
                raise FileOperationError(
                    f"Cannot create target directory '{target_parent_dir}': {e}"
                ) from e

        archive_base_name_no_ext = os.path.splitext(target_mcworld_file_path)[0]
        temp_zip_path = archive_base_name_no_ext + ".zip"

        try:
            self.logger.debug(
                f"Creating temporary ZIP archive at '{archive_base_name_no_ext}' for world '{world_dir_name}'."
            )
            # Create a zip archive of the world directory's contents.
            shutil.make_archive(
                base_name=archive_base_name_no_ext,
                format="zip",
                root_dir=full_source_world_dir,
                base_dir=".",
            )
            self.logger.debug(f"Successfully created temporary ZIP: {temp_zip_path}")

            if not os.path.exists(temp_zip_path):
                raise BackupRestoreError(
                    f"Archive process completed but temp zip '{temp_zip_path}' not found."
                )

            # Rename the .zip to .mcworld, overwriting if necessary.
            if os.path.exists(target_mcworld_file_path):
                self.logger.warning(
                    f"Target file '{target_mcworld_file_path}' exists. Overwriting."
                )
                os.remove(target_mcworld_file_path)
            os.rename(temp_zip_path, target_mcworld_file_path)
            self.logger.info(
                f"Server '{self.server_name}': World export successful. Created: {target_mcworld_file_path}"
            )

        except OSError as e:
            if os.path.exists(temp_zip_path):
                os.remove(temp_zip_path)  # Clean up temporary file on failure.
            raise BackupRestoreError(
                f"Failed to create .mcworld for server '{self.server_name}', world '{world_dir_name}': {e}"
            ) from e
        except Exception as e_unexp:
            if os.path.exists(temp_zip_path):
                os.remove(temp_zip_path)  # Clean up temporary file on failure.
            raise BackupRestoreError(
                f"Unexpected error exporting world for server '{self.server_name}', world '{world_dir_name}': {e_unexp}"
            ) from e_unexp

    def import_active_world_from_mcworld(self, mcworld_backup_file_path: str) -> str:
        """Imports a ``.mcworld`` file, replacing the server's currently active world.

        .. warning::
            This is a **DESTRUCTIVE** operation. The existing active world directory
            will be deleted before the new world is imported.

        This method first determines the name of the server's active world by
        calling ``self.get_world_name()`` (expected from
        :class:`~.core.server.state_mixin.ServerStateMixin`). It then uses
        :meth:`.extract_mcworld_to_directory` to extract the contents of the
        provided `mcworld_backup_file_path` into a directory with that active
        world name, effectively replacing it.

        Args:
            mcworld_backup_file_path (str): The absolute path to the source
                ``.mcworld`` file that contains the world data to import.

        Returns:
            str: The name of the world directory (which is the active world name)
            that the ``.mcworld`` file was imported into.

        Raises:
            MissingArgumentError: If `mcworld_backup_file_path` is empty or not a string.
            AppFileNotFoundError: If the source `mcworld_backup_file_path` does not exist.
            BackupRestoreError: If any part of the import process fails, including
                failure to determine the active world name, or errors during
                extraction (which can wrap :class:`~.error.ExtractError`,
                :class:`~.error.FileOperationError`, etc.).
            AttributeError: If ``get_world_name()`` is missing.
        """
        if (
            not isinstance(mcworld_backup_file_path, str)
            or not mcworld_backup_file_path
        ):
            raise MissingArgumentError(
                ".mcworld backup file path cannot be empty and must be a string."
            )

        mcworld_filename = os.path.basename(mcworld_backup_file_path)
        self.logger.info(
            f"Server '{self.server_name}': Importing active world from backup '{mcworld_filename}'."
        )

        if not os.path.isfile(mcworld_backup_file_path):
            raise AppFileNotFoundError(mcworld_backup_file_path, ".mcworld backup file")

        # 1. Determine the target active world directory name.
        try:
            # This method is expected to be on the final class from StateMixin.
            active_world_dir_name = self.get_world_name()
            self.logger.info(
                f"Target active world name for server '{self.server_name}' is '{active_world_dir_name}'."
            )
        except (AppFileNotFoundError, ConfigParseError, Exception) as e:
            raise BackupRestoreError(
                f"Cannot import world: Failed to get active world name for '{self.server_name}'."
            ) from e

        # 2. Delegate the extraction to the specialized method.
        try:
            self.extract_mcworld_to_directory(
                mcworld_backup_file_path, active_world_dir_name
            )
            self.logger.info(
                f"Server '{self.server_name}': Active world import from '{mcworld_filename}' completed successfully into '{active_world_dir_name}'."
            )
            return active_world_dir_name
        except (
            AppFileNotFoundError,
            ExtractError,
            FileOperationError,
            MissingArgumentError,
            Exception,
        ) as e_extract:
            raise BackupRestoreError(
                f"World import for server '{self.server_name}' failed into '{active_world_dir_name}': {e_extract}"
            ) from e_extract

    def delete_active_world_directory(self) -> bool:
        """Deletes the server's currently active world directory.

        .. warning::
            This is a **DESTRUCTIVE** operation. The active world's data will be
            permanently removed. The server will typically generate a new world
            with the same name on its next startup if the ``level-name`` in
            ``server.properties`` is not changed.

        This method determines the active world's directory path using
        :meth:`._get_active_world_directory_path` and then uses the robust
        deletion utility :func:`~.core.system.base.delete_path_robustly`
        to remove it.

        Returns:
            bool: ``True`` if the active world directory was successfully deleted
            or if it did not exist initially.

        Raises:
            FileOperationError: If determining the world path fails (e.g., due to
                issues with ``server.properties`` or if the path is not a directory),
                or if the deletion itself fails critically (though
                `delete_path_robustly` attempts to handle many common issues).
            AppFileNotFoundError: If ``server.properties`` is missing (propagated
                from :meth:`._get_active_world_directory_path` via `get_world_name`).
            ConfigParseError: If ``level-name`` is missing from ``server.properties``
                (propagated).
            AttributeError: If ``get_world_name()`` method (from StateMixin)
                is not available.
        """
        try:
            active_world_dir = self._get_active_world_directory_path()
            active_world_name = os.path.basename(active_world_dir)
        except (AppFileNotFoundError, ConfigParseError, Exception) as e:
            self.logger.error(
                f"Server '{self.server_name}': Cannot delete active world, failed to determine path: {e}"
            )
            raise

        self.logger.warning(
            f"Server '{self.server_name}': Attempting to delete active world directory: '{active_world_dir}'. THIS IS A DESTRUCTIVE operation."
        )

        if not os.path.exists(active_world_dir):
            self.logger.info(
                f"Server '{self.server_name}': Active world directory '{active_world_dir}' does not exist. Nothing to delete."
            )
            return True

        if not os.path.isdir(active_world_dir):
            raise FileOperationError(
                f"Path for active world '{active_world_name}' is not a directory: {active_world_dir}"
            )

        # Use the robust deletion utility from the system module.
        success = system_base_utils.delete_path_robustly(
            active_world_dir,
            f"active world directory '{active_world_name}' for server '{self.server_name}'",
        )

        if success:
            self.logger.info(
                f"Server '{self.server_name}': Successfully deleted active world directory '{active_world_dir}'."
            )
        else:
            # The robust utility already logs errors, but we raise to signal failure.
            raise FileOperationError(
                f"Failed to completely delete active world directory '{active_world_name}' for server '{self.server_name}'. Check logs."
            )

        return success

    @property
    def world_icon_filename(self) -> str:
        """str: The standard filename for a world's icon image (``world_icon.jpeg``)."""
        return "world_icon.jpeg"

    @property
    def world_icon_filesystem_path(self) -> Optional[str]:
        """Optional[str]: The absolute filesystem path to the world icon for the active world.

        This is constructed by joining the active world's directory path (from
        :meth:`._get_active_world_directory_path`) with the standard icon filename
        (:attr:`.world_icon_filename`).

        Returns ``None`` if the active world directory path cannot be determined
        (e.g., if ``get_world_name()`` fails or is unavailable).
        """
        try:
            active_world_dir = self._get_active_world_directory_path()
            return os.path.join(active_world_dir, self.world_icon_filename)
        except (AppFileNotFoundError, ConfigParseError, Exception) as e:
            self.logger.warning(
                f"Server '{self.server_name}': Cannot determine world icon path because active world name is unavailable: {e}"
            )
            return None

    def has_world_icon(self) -> bool:
        """Checks if the standard world icon file (``world_icon.jpeg``) exists for the active world.

        This method uses :attr:`.world_icon_filesystem_path` to determine the
        expected location of the icon and checks if a file exists at that path.

        Returns:
            bool: ``True`` if the world icon file exists and is a regular file,
            ``False`` otherwise (e.g., path cannot be determined, file does not
            exist, or is not a file).
        """
        icon_path = self.world_icon_filesystem_path
        if icon_path and os.path.isfile(icon_path):
            self.logger.debug(
                f"Server '{self.server_name}': World icon found at '{icon_path}'."
            )
            return True

        # Log if path was determined but file not found/not a file
        if icon_path:  # Implies get_world_name succeeded
            self.logger.debug(
                f"Server '{self.server_name}': World icon not found or is not a file at determined path '{icon_path}'."
            )
        # If icon_path is None, _get_active_world_directory_path (via world_icon_filesystem_path)
        # would have already logged a warning if get_world_name failed.
        return False
