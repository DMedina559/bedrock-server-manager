import glob
import logging
import os
from typing import List

from bedrock_server_manager.error import AppFileNotFoundError, FileOperationError

logger = logging.getLogger(__name__)


class ContentMixin:
    """
    Mixin class for BedrockServerManager that handles global content management.
    """

    def _list_content_files(self, sub_folder: str, extensions: List[str]) -> List[str]:
        """
        Internal helper to list files with specified extensions from a sub-folder
        within the global content directory.

        This method constructs a path to ``<content_dir>/<sub_folder>``, then
        scans this directory for files matching any of the provided ``extensions``.
        The global content directory is defined by ``settings['paths.content']``
        and cached in :attr:`._content_dir`.

        Args:
            sub_folder (str): The name of the sub-folder within the global content
                directory to scan (e.g., "worlds", "addons").
            extensions (List[str]): A list of file extensions to search for.
                Extensions should include the leading dot (e.g., ``[".mcworld"]``,
                ``[".mcpack", ".mcaddon"]``).

        Returns:
            List[str]: A sorted list of absolute paths to the files found.
            Returns an empty list if the target directory does not exist or no
            matching files are found.

        Raises:
            AppFileNotFoundError: If the main content directory (:attr:`._content_dir`)
                is not configured or does not exist as a directory.
            FileOperationError: If an OS-level error occurs while scanning the
                directory (e.g., permission issues).
        """
        if not self._content_dir or not os.path.isdir(self._content_dir):
            raise AppFileNotFoundError(str(self._content_dir), "Content directory")

        target_dir = os.path.join(self._content_dir, sub_folder)
        if not os.path.isdir(target_dir):
            logger.debug(
                f"BSM: Content sub-directory '{target_dir}' not found. Returning empty list."
            )
            return []

        found_files: List[str] = []
        for ext in extensions:
            pattern = f"*{ext}" if ext.startswith(".") else f"*.{ext}"
            try:
                for filepath in glob.glob(os.path.join(target_dir, pattern)):
                    if os.path.isfile(filepath):
                        found_files.append(os.path.abspath(filepath))
            except OSError as e:
                raise FileOperationError(
                    f"Error scanning content directory {target_dir}: {e}"
                ) from e
        return sorted(list(set(found_files)))

    def list_available_worlds(self) -> List[str]:
        """Lists available ``.mcworld`` template files from the global content directory.

        This method scans the ``worlds`` sub-folder within the application's
        global content directory (see :attr:`._content_dir` and
        ``settings['paths.content']``) for files with the ``.mcworld`` extension.
        It relies on :meth:`._list_content_files` for the actual scanning.

        These ``.mcworld`` files typically represent world templates that can be
        imported to create new server worlds or overwrite existing ones.

        Returns:
            List[str]: A sorted list of absolute paths to all found ``.mcworld`` files.
            Returns an empty list if the directory doesn't exist or no ``.mcworld``
            files are present.

        Raises:
            AppFileNotFoundError: If the main content directory is not configured
                or found (from :meth:`._list_content_files`).
            FileOperationError: If an OS error occurs during directory scanning
                (from :meth:`._list_content_files`).
        """
        return self._list_content_files("worlds", [".mcworld"])

    def list_available_addons(self) -> List[str]:
        """Lists available addon files (``.mcpack``, ``.mcaddon``) from the global content directory.

        This method scans the ``addons`` sub-folder within the application's
        global content directory (see :attr:`._content_dir` and
        ``settings['paths.content']``) for files with ``.mcpack`` or
        ``.mcaddon`` extensions. It uses :meth:`._list_content_files` for scanning.

        These files represent behavior packs, resource packs, or bundled addons
        that can be installed onto server instances.

        Returns:
            List[str]: A sorted list of absolute paths to all found ``.mcpack``
            and ``.mcaddon`` files. Returns an empty list if the directory
            doesn't exist or no such files are present.

        Raises:
            AppFileNotFoundError: If the main content directory is not configured
                or found (from :meth:`._list_content_files`).
            FileOperationError: If an OS error occurs during directory scanning
                (from :meth:`._list_content_files`).
        """
        return self._list_content_files("addons", [".mcpack", ".mcaddon"])
