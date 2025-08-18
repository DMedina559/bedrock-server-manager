# bedrock_server_manager/core/downloader.py
"""Manages downloading, extracting, and maintaining Minecraft Bedrock Server files.

This module is central to acquiring the necessary files for running a Minecraft
Bedrock server. It provides functionalities to:

    - Fetch the latest or specific versions of the Bedrock Server software for
      Linux and Windows.
    - Download the server software from official sources, using the Minecraft
      download API as the primary method.
    - Extract the downloaded server files into a designated server directory, with
      options for preserving existing configuration, worlds, and data during updates.
    - Manage a local cache of downloaded server ZIP files, including pruning old
      versions to save disk space.

Key Components:

    - :class:`BedrockDownloader`: A class that orchestrates the download and setup
      process for a single server instance. It handles version resolution,
      downloading, extraction, and local cache pruning related to its operation.
    - :func:`prune_old_downloads`: A standalone utility function to clean up
      old downloaded server ZIP files from a specified directory, independent
      of a specific `BedrockDownloader` instance.

The module aims to provide a robust and error-handled way to obtain server files,
dealing with potential network issues, file system operations, and changes in
download URLs or API responses.
"""

import re
import requests
import platform
import logging
import os
import json
import zipfile
from pathlib import Path
from typing import Tuple, Optional, Set, TYPE_CHECKING

# Local application imports.
from .system import base as system_base
from ..error import (
    DownloadError,
    ExtractError,
    MissingArgumentError,
    InternetConnectivityError,
    FileOperationError,
    AppFileNotFoundError,
    ConfigurationError,
    UserInputError,
    SystemError,
)

if TYPE_CHECKING:
    from ..config.settings import Settings

logger = logging.getLogger(__name__)


def prune_old_downloads(download_dir: str, download_keep: int):
    """Removes the oldest downloaded server ZIP files from a directory.

    This function keeps a specified number of the most recent downloads and
    deletes the rest to manage disk space.

    Args:
        download_dir: The directory containing the downloaded
            ``bedrock-server-*.zip`` files.
        download_keep: The number of most recent ZIP files to retain.

    Raises:
        MissingArgumentError: If `download_dir` is not provided.
        UserInputError: If `download_keep` is not a non-negative integer.
        AppFileNotFoundError: If `download_dir` does not exist.
        FileOperationError: If there's an error accessing or deleting files.
    """
    if not download_dir:
        raise MissingArgumentError("Download directory cannot be empty for pruning.")
    if not isinstance(download_keep, int) or download_keep < 0:
        raise UserInputError(
            f"Invalid value for downloads to keep: '{download_keep}'. Must be an integer >= 0."
        )

    logger.debug(f"Configured to keep {download_keep} downloads in '{download_dir}'.")

    if not os.path.isdir(download_dir):
        # Log a warning and return if the directory doesn't exist, as it's not a critical error for pruning.
        logger.warning(
            f"Download directory '{download_dir}' not found. Skipping pruning."
        )
        return

    logger.info(
        f"Pruning old Bedrock server downloads in '{download_dir}' (keeping {download_keep})..."
    )

    try:
        dir_path = Path(download_dir)
        # Find all files matching the bedrock server download pattern.
        # Using rglob to catch files in subdirectories if any were accidentally created,
        # though typically downloads are flat in their respective 'stable'/'preview' dirs.
        download_files = list(dir_path.glob("bedrock-server-*.zip"))

        # Sort files by modification time (newest first) to identify which to keep.
        download_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        logger.debug(
            f"Found {len(download_files)} potential download files matching pattern in '{download_dir}'."
        )

        if len(download_files) > download_keep:
            files_to_delete = download_files[download_keep:]
            logger.info(
                f"Found {len(download_files)} downloads in '{download_dir}'. Will delete {len(files_to_delete)} oldest file(s) to keep {download_keep}."
            )

            deleted_count = 0
            failed_deletions = []
            for file_path_obj in files_to_delete:
                try:
                    file_path_obj.unlink()
                    logger.info(f"Deleted old download: {file_path_obj}")
                    deleted_count += 1
                except OSError as e_unlink:
                    logger.error(
                        f"Failed to delete old server download '{file_path_obj}': {e_unlink}",
                        exc_info=True,
                    )
                    failed_deletions.append(str(file_path_obj))

            if failed_deletions:
                # If some deletions failed, log a warning but don't necessarily raise an error
                # as pruning is a maintenance task and shouldn't block primary operations.
                logger.warning(
                    f"Failed to delete {len(failed_deletions)} old download(s) in '{download_dir}': {', '.join(failed_deletions)}. Check logs."
                )
            if deleted_count > 0:
                logger.info(
                    f"Successfully deleted {deleted_count} old download(s) from '{download_dir}'."
                )
            elif (
                not failed_deletions
            ):  # No deletions needed or no files to delete beyond retention
                logger.info(
                    f"No files were deleted from '{download_dir}' as part of this pruning operation."
                )
        else:
            logger.info(
                f"Found {len(download_files)} download(s) in '{download_dir}', which is not more than the {download_keep} to keep. No files deleted."
            )

    except OSError as e_os:
        # Log as warning, pruning failures are not usually critical.
        logger.warning(
            f"Error accessing or processing files for pruning in '{download_dir}': {e_os}",
            exc_info=True,
        )
    except Exception as e_generic:
        logger.error(
            f"Unexpected error during pruning operation for '{download_dir}': {e_generic}",
            exc_info=True,
        )


class BedrockDownloader:
    """Manages the download, extraction, and setup of a Bedrock Server instance.

    This class orchestrates the process of obtaining and preparing Minecraft
    Bedrock server files for a specific server instance. It handles:

        - **Version Targeting**: Allows specifying "LATEST" (stable), "PREVIEW", or a
          concrete version number (e.g., "1.20.10.01", "1.20.10.01-PREVIEW").
        - **URL Resolution**: Primarily uses the official Minecraft download API to find
          the correct download URL for the target version and operating system (Linux/Windows).
        - **Downloading**: Downloads the server ZIP archive from the resolved URL,
          saving it to a version-specific (stable/preview) subdirectory within the
          configured global downloads path. It skips downloading if the file already exists.
        - **Extraction**: Extracts the contents of the downloaded ZIP archive into the
          specified server directory. It supports "fresh install" and "update" modes,
          where the latter preserves user data like worlds, properties, and allowlists.
        - **Cache Pruning**: After a download, it can trigger pruning of older ZIP files
          within its specific download subdirectory (stable or preview) based on retention settings.

    An instance of this class is typically created when a new server needs to be
    installed or an existing one updated.

    Attributes:
        settings (Settings): The application settings object.
        server_dir (str): The absolute path to the target server directory.
        input_target_version (str): The user-provided version string.
        os_name (str): The name of the current operating system (e.g., "Linux", "Windows").
        base_download_dir (Optional[str]): The root directory for all downloads.
        resolved_download_url (Optional[str]): The final URL used for downloading.
        actual_version (Optional[str]): The specific version number resolved (e.g., "1.20.10.01").
        zip_file_path (Optional[str]): Full path to the downloaded server ZIP file.
        specific_download_dir (Optional[str]): Path to the subdirectory within
            `base_download_dir` used for this instance's downloads (e.g., ".../downloads/stable").
    """

    PRESERVED_ITEMS_ON_UPDATE: Set[str] = {
        "worlds/",
        "allowlist.json",
        "permissions.json",
        "server.properties",
    }

    def __init__(
        self,
        settings_obj: "Settings",
        server_dir: str,
        target_version: str = "LATEST",
        server_zip_path: Optional[str] = None,
    ):
        """Initializes the BedrockDownloader.

        Args:
            settings_obj (Settings): The application's ``Settings`` object,
                providing access to configuration like download paths.
            server_dir (str): The target directory where the server files will be
                installed or updated. This path will be converted to an absolute path.
            target_version (str, optional): The version identifier for the server
                to download. Defaults to "LATEST".
                Examples: "LATEST", "PREVIEW", "CUSTOM", "1.20.10.01", "1.20.10.01-PREVIEW".
            server_zip_path (str, optional): Absolute path to a custom server ZIP file.
                Required if `target_version` is "CUSTOM".
        Raises:
            MissingArgumentError: If `settings_obj`, `server_dir`, or
                `target_version` are not provided or are empty.
            ConfigurationError: If the `paths.downloads` setting is missing or
                empty in the provided `settings_obj`.
        """
        if not settings_obj:
            raise MissingArgumentError(
                "Settings object cannot be empty for BedrockDownloader."
            )
        if not server_dir:
            raise MissingArgumentError(
                "Server directory cannot be empty for BedrockDownloader."
            )
        if not target_version:
            raise MissingArgumentError(
                "Target version cannot be empty for BedrockDownloader."
            )

        self.settings: "Settings" = settings_obj
        self.server_dir: str = os.path.abspath(server_dir)
        self.input_target_version: str = target_version.strip()
        self.logger = logging.getLogger(__name__)

        # For "CUSTOM" version, the path to the ZIP file must be provided.
        if self.input_target_version.upper() == "CUSTOM":
            if not server_zip_path or not os.path.isabs(server_zip_path):
                raise MissingArgumentError(
                    "Absolute path to server ZIP file is required for CUSTOM version."
                )
            if not os.path.exists(server_zip_path):
                raise AppFileNotFoundError(
                    server_zip_path, "Custom server ZIP file not found"
                )
            self.server_zip_path = server_zip_path
        else:
            self.server_zip_path = None

        self.os_name: str = platform.system()
        self.base_download_dir: Optional[str] = self.settings.get("paths.downloads")
        if not self.base_download_dir:
            raise ConfigurationError(
                "DOWNLOAD_DIR setting is missing or empty in configuration."
            )
        self.base_download_dir = os.path.abspath(self.base_download_dir)

        # These attributes are populated during the download process.
        self.resolved_download_url: Optional[str] = None
        self.actual_version: Optional[str] = (
            None  # The final version string, e.g., "1.20.10.01"
        )
        self.zip_file_path: Optional[str] = None
        self.specific_download_dir: Optional[str] = None  # e.g., .../downloads/stable

        # These attributes are derived from the input_target_version.
        self._version_type: str = ""  # "LATEST" or "PREVIEW"
        self._custom_version_number: str = ""  # "X.Y.Z.W" part if provided

        self._determine_version_parameters()

    def _determine_version_parameters(self):
        """Parses the ``input_target_version`` string to set internal parameters.

        This method analyzes the ``self.input_target_version`` attribute to
        determine if the target is "LATEST" (stable), "PREVIEW", a specific
        stable version number (e.g., "1.20.10.01"), or a specific preview
        version number (e.g., "1.20.10.01-PREVIEW").

        It populates the following internal attributes:

            - ``self._version_type``: Set to "LATEST" or "PREVIEW".
            - ``self._custom_version_number``: Set to the version number string
              (e.g., "1.20.10.01") if a specific version is targeted, otherwise empty.

        """
        target_upper = self.input_target_version.upper()
        if target_upper == "CUSTOM":
            self._version_type = "CUSTOM"
            self.logger.info(
                f"Instance targeting CUSTOM version for server: {self.server_dir}"
            )
        elif target_upper == "PREVIEW":
            self._version_type = "PREVIEW"
            self.logger.info(
                f"Instance targeting latest PREVIEW version for server: {self.server_dir}"
            )
        elif target_upper == "LATEST":
            self._version_type = "LATEST"
            self.logger.info(
                f"Instance targeting latest STABLE version for server: {self.server_dir}"
            )
        elif target_upper.endswith("-PREVIEW"):
            self._version_type = "PREVIEW"
            self._custom_version_number = self.input_target_version[: -len("-PREVIEW")]
            self.logger.info(
                f"Instance targeting specific PREVIEW version '{self._custom_version_number}' for server: {self.server_dir}"
            )
        else:
            self._version_type = "LATEST"  # Assume a specific stable version
            self._custom_version_number = self.input_target_version
            self.logger.info(
                f"Instance targeting specific STABLE version '{self._custom_version_number}' for server: {self.server_dir}"
            )

    def _lookup_bedrock_download_url(self) -> str:
        """Finds the download URL by querying the official Minecraft download API.

        This is the most reliable method as it does not rely on web scraping.

        Returns:
            The resolved download URL for the specified version and OS.

        Raises:
            SystemError: If the operating system is not supported.
            InternetConnectivityError: If the API cannot be reached.
            DownloadError: If the API response is invalid or does not contain
                the required URL.
        """
        self.logger.debug(
            f"Looking up download URL for target: '{self.input_target_version}'"
        )
        API_URL = (
            "https://net-secondary.web.minecraft-services.net/api/v1.0/download/links"
        )

        # 1. Determine the API identifier based on OS and version type.
        if self.os_name == "Linux":
            download_type = (
                "serverBedrockPreviewLinux"
                if self._version_type == "PREVIEW"
                else "serverBedrockLinux"
            )
        elif self.os_name == "Windows":
            download_type = (
                "serverBedrockPreviewWindows"
                if self._version_type == "PREVIEW"
                else "serverBedrockWindows"
            )
        else:
            raise SystemError(
                f"Unsupported OS for Bedrock server download: {self.os_name}"
            )
        self.logger.debug(f"Targeting API downloadType identifier: '{download_type}'")

        # 2. Fetch data from the API.
        try:
            app_name = self.settings.get("_app_name", "BedrockServerManager")
            headers = {
                "User-Agent": f"Python/{platform.python_version()} {app_name}/UnknownVersion"
            }
            response = requests.get(API_URL, headers=headers, timeout=30)
            response.raise_for_status()
            api_data = response.json()
            self.logger.debug(f"Successfully fetched API data: {api_data}")
        except requests.exceptions.RequestException as e:
            raise InternetConnectivityError(
                f"Could not contact the Minecraft download API: {e}"
            ) from e
        except json.JSONDecodeError as e:
            raise DownloadError(
                "The Minecraft download API returned malformed data."
            ) from e

        # 3. Find the correct download link in the response.
        all_links = api_data.get("result", {}).get("links", [])
        base_url = next(
            (
                link.get("downloadUrl")
                for link in all_links
                if link.get("downloadType") == download_type
            ),
            None,
        )

        if not base_url:
            self.logger.error(
                f"API response did not contain a URL for downloadType '{download_type}'."
            )
            raise DownloadError(
                f"The API did not provide a download URL for your system ({download_type})."
            )
        self.logger.info(f"Found URL via API for '{download_type}': {base_url}")

        # 4. If a specific version was requested, substitute it into the URL.
        if self._custom_version_number:
            try:
                modified_url = re.sub(
                    r"(bedrock-server-)[0-9.]+?(\.zip)",
                    rf"\g<1>{self._custom_version_number}\g<2>",
                    base_url,
                    count=1,
                )
                if (
                    modified_url == base_url
                    and self._custom_version_number not in base_url
                ):
                    raise DownloadError(
                        f"Failed to construct URL for specific version '{self._custom_version_number}'. The URL format may have changed."
                    )
                self.resolved_download_url = modified_url
                self.logger.info(
                    f"Constructed specific version URL: {self.resolved_download_url}"
                )
            except Exception as e:
                raise DownloadError(
                    f"Error constructing URL for specific version '{self._custom_version_number}': {e}"
                ) from e
        else:
            self.resolved_download_url = base_url

        if not self.resolved_download_url:
            raise DownloadError(
                "Internal error: Failed to resolve a final download URL."
            )
        return self.resolved_download_url

    def _get_version_from_url(self) -> str:
        """Extracts the version number from the resolved download URL or custom zip path.
        This method populates `self.actual_version`.
        Returns:
            The extracted version string (e.g., "1.20.10.01").
        Raises:
            MissingArgumentError: If the download URL has not been resolved yet.
            DownloadError: If the URL format is unexpected and the version
                cannot be parsed.
        """
        source_path = (
            self.server_zip_path
            if self._version_type == "CUSTOM"
            else self.resolved_download_url
        )

        if not source_path:
            raise MissingArgumentError(
                "Download URL or custom zip path is not set. Cannot extract version."
            )

        # First, try to match the official bedrock-server-X.Y.Z.W.zip format
        match = re.search(r"bedrock-server-([0-9.]+)\.zip", source_path)
        if match:
            version = match.group(1).rstrip(".")
            self.logger.debug(
                f"Extracted version '{version}' from standard path format: {source_path}"
            )
            self.actual_version = version
            return self.actual_version

        # If it's a custom zip, try a more general version extraction
        if self._version_type == "CUSTOM":
            # Try to find any version-like number in the filename (e.g., 1.0.0, 2.3.4.5)
            match = re.search(r"(\d+\.\d+\.\d+(\.\d+)?)", Path(source_path).name)
            if match:
                version = match.group(1)
                self.logger.debug(
                    f"Extracted version '{version}' from custom ZIP name: {source_path}"
                )
                self.actual_version = version
                return self.actual_version
            else:
                # Fallback for custom zips that don't have a clear version number
                custom_version = Path(source_path).stem
                self.logger.warning(
                    f"Could not parse a version number from custom ZIP '{source_path}'. "
                    f"Using filename stem '{custom_version}' as version."
                )
                self.actual_version = custom_version
                return self.actual_version

        # If it's not a custom zip and didn't match the standard format, it's an error
        raise DownloadError(
            f"Failed to extract version number from URL format: {source_path}"
        )

    def _download_server_zip_file(self):
        """Downloads the server ZIP file from the resolved URL.

        Raises:
            MissingArgumentError: If the URL or target file path are not set.
            FileOperationError: If directories cannot be created or the file
                cannot be written.
            InternetConnectivityError: If the download request fails.
        """
        if not self.resolved_download_url or not self.zip_file_path:
            raise MissingArgumentError(
                "Download URL or ZIP file path not set. Cannot download."
            )

        self.logger.info(
            f"Attempting to download server from: {self.resolved_download_url}"
        )
        self.logger.debug(f"Saving downloaded file to: {self.zip_file_path}")

        target_dir = os.path.dirname(self.zip_file_path)
        try:
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Cannot create directory '{target_dir}' for download: {e}"
            ) from e

        try:
            app_name = self.settings.get("_app_name", "BedrockServerManager")
            headers = {
                "User-Agent": f"Python Requests/{requests.__version__} ({app_name})"
            }
            # Use a streaming request to handle large files efficiently.
            with requests.get(
                self.resolved_download_url, headers=headers, stream=True, timeout=120
            ) as response:
                response.raise_for_status()
                self.logger.debug(
                    f"Download request successful (status {response.status_code}). Writing to file."
                )
                total_size = int(response.headers.get("content-length", 0))
                bytes_written = 0
                with open(self.zip_file_path, "wb") as f:
                    # Write the file in chunks to avoid high memory usage.
                    for chunk in response.iter_content(chunk_size=8192 * 4):
                        f.write(chunk)
                        bytes_written += len(chunk)
                self.logger.info(
                    f"Successfully downloaded {bytes_written} bytes to: {self.zip_file_path}"
                )
                if total_size != 0 and bytes_written != total_size:
                    self.logger.warning(
                        f"Downloaded size ({bytes_written}) does not match content-length ({total_size}). File might be incomplete."
                    )
        except requests.exceptions.RequestException as e:
            # Clean up partial download on failure.
            if os.path.exists(self.zip_file_path):
                try:
                    os.remove(self.zip_file_path)
                except OSError as rm_err:
                    self.logger.warning(
                        f"Could not remove incomplete file '{self.zip_file_path}': {rm_err}"
                    )
            raise InternetConnectivityError(
                f"Download failed for '{self.resolved_download_url}': {e}"
            ) from e
        except OSError as e:
            raise FileOperationError(
                f"Cannot write to file '{self.zip_file_path}': {e}"
            ) from e
        except Exception as e:
            raise FileOperationError(f"Unexpected error during download: {e}") from e

    def _execute_instance_pruning(self):
        """Executes download cache pruning for this downloader instance.

        This method calls the global :func:`prune_old_downloads` function,
        passing the instance's specific download directory (e.g.,
        ``.../downloads/stable`` or ``.../downloads/preview``) and the
        configured retention policy from settings (``retention.downloads``).

        Pruning failures are logged as warnings and do not interrupt the main
        download or setup operations, as pruning is a non-critical maintenance task.
        """
        if self._version_type == "CUSTOM":
            self.logger.debug("Skipping pruning for CUSTOM version.")
            return

        if not self.specific_download_dir:
            self.logger.debug(
                "Instance's specific_download_dir not set, skipping instance pruning."
            )
            return
        if not self.settings:
            self.logger.warning(
                "Instance settings not available, skipping instance pruning."
            )
            return

        try:
            keep_setting = self.settings.get("retention.downloads", 3)
            effective_keep = int(keep_setting)
            if effective_keep < 0:
                self.logger.error(
                    f"Invalid DOWNLOAD_KEEP setting ('{keep_setting}'). Must be >= 0. Skipping."
                )
                return
            self.logger.debug(
                f"Instance triggering pruning for '{self.specific_download_dir}' keeping {effective_keep} files."
            )
            prune_old_downloads(self.specific_download_dir, effective_keep)
        except (
            UserInputError,
            FileOperationError,
            AppFileNotFoundError,
            MissingArgumentError,
            Exception,
        ) as e:
            # Log as a warning and continue, as pruning failure should not block the main operation.
            self.logger.warning(
                f"Pruning failed for instance's directory '{self.specific_download_dir}': {e}. Continuing main operation.",
                exc_info=True,
            )

    def get_version_for_target_spec(self) -> str:
        """Resolves and returns the actual version string for the instance's target.

        This method orchestrates the lookup of the download URL (via
        :meth:`._lookup_bedrock_download_url`) and the extraction of the version
        number from that URL (via :meth:`._get_version_from_url`). It populates
        instance attributes ``self.actual_version`` and
        ``self.resolved_download_url`` as side effects.

        This method primarily focuses on identifying the version and its download
        source without actually downloading the server files.

        Returns:
            str: The actual, resolved version string (e.g., "1.20.10.01")
            corresponding to the initial target specification.

        Raises:
            SystemError: If the OS is unsupported (from :meth:`._lookup_bedrock_download_url`).
            InternetConnectivityError: If network issues prevent API access (from
                :meth:`._lookup_bedrock_download_url`).
            DownloadError: If the API response is invalid, the URL cannot be
                found or constructed, or if the version cannot be parsed from the URL.
        """
        self.logger.debug(
            f"Getting prospective version for target spec: '{self.input_target_version}'"
        )
        if self._version_type == "CUSTOM":
            self.logger.debug("Custom version specified, skipping download URL lookup.")
            self._get_version_from_url()
        else:
            # 1. Resolve the download URL.
            self._lookup_bedrock_download_url()
            # 2. Parse the version from the resolved URL.
            self._get_version_from_url()

        # 3. Return the result.
        if not self.actual_version:
            raise DownloadError("Could not determine actual version from resolved URL.")
        return self.actual_version

    def prepare_download_assets(self) -> Tuple[str, str, str]:
        """Orchestrates the download preparation, including potential download.

        This comprehensive method coordinates all steps required to make the server
        ZIP file available locally, prior to extraction. The steps include:

            1.  Checking for internet connectivity using :func:`system_base.check_internet_connectivity`.
            2.  Ensuring the main server directory (``self.server_dir``) and the base
                download directory (``self.base_download_dir``) exist, creating them
                if necessary.
            3.  Resolving the actual version and download URL by calling
                :meth:`.get_version_for_target_spec()`. This populates
                ``self.actual_version`` and ``self.resolved_download_url``.
            4.  Determining the specific download subdirectory (e.g., ``.../downloads/stable``
                or ``.../downloads/preview``) and ensuring it exists. This sets
                ``self.specific_download_dir``.
            5.  Constructing the full path to the target ZIP file (``self.zip_file_path``).
            6.  If the ZIP file does not already exist at ``self.zip_file_path``, it
                downloads the file using :meth:`._download_server_zip_file()`.
            7.  Finally, it triggers cache pruning for the specific download directory
                using :meth:`._execute_instance_pruning()`.

        Returns:
            Tuple[str, str, str]: A tuple containing:
                - ``actual_version`` (str): The resolved version string (e.g., "1.20.10.01").
                - ``zip_file_path`` (str): The absolute path to the downloaded (or pre-existing)
                  server ZIP file.
                - ``specific_download_dir`` (str): The absolute path to the specific
                  download subdirectory used (e.g., ".../downloads/stable").

        Raises:
            InternetConnectivityError: If internet is unavailable or if download fails.
            FileOperationError: If directory creation or file writing fails.
            DownloadError: If version/URL resolution fails, or if critical attributes
                           are not set post-preparation.
            SystemError: Propagated from version resolution if OS is unsupported.
        """
        self.logger.info(
            f"Starting Bedrock server download preparation for directory: '{self.server_dir}'"
        )

        # For CUSTOM version, we use a local file, so we skip most of the download logic.
        if self._version_type == "CUSTOM":
            self.logger.info(
                f"Custom version specified. Using local ZIP: {self.server_zip_path}"
            )
            if not self.server_zip_path:
                raise MissingArgumentError(
                    "server_zip_path is required for CUSTOM version."
                )

            # Set the zip_file_path and actual_version from the custom path.
            self.zip_file_path = self.server_zip_path
            self._get_version_from_url()

            # The specific_download_dir for a custom zip is its parent directory.
            self.specific_download_dir = str(Path(self.server_zip_path).parent)
            self.logger.debug(
                f"Setting specific_download_dir for custom zip to: {self.specific_download_dir}"
            )

            if (
                not self.actual_version
                or not self.zip_file_path
                or not self.specific_download_dir
            ):
                raise DownloadError(
                    "Critical state missing after custom ZIP preparation."
                )

            return self.actual_version, self.zip_file_path, self.specific_download_dir

        system_base.check_internet_connectivity()

        try:
            os.makedirs(self.server_dir, exist_ok=True)
            if self.base_download_dir:
                os.makedirs(self.base_download_dir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Failed to create required directories: {e}"
            ) from e

        # This resolves URL and version, populating instance attributes.
        self.get_version_for_target_spec()

        if (
            not self.actual_version
            or not self.resolved_download_url
            or not self.base_download_dir
        ):
            raise DownloadError(
                "Internal error: version or URL not resolved after lookup."
            )

        # Determine the specific subdirectory (stable or preview).
        version_subdir_name = "preview" if self._version_type == "PREVIEW" else "stable"
        self.specific_download_dir = os.path.join(
            self.base_download_dir, version_subdir_name
        )
        self.logger.debug(
            f"Using specific download subdirectory: {self.specific_download_dir}"
        )
        try:
            os.makedirs(self.specific_download_dir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Failed to create download subdirectory '{self.specific_download_dir}': {e}"
            ) from e

        self.zip_file_path = os.path.join(
            self.specific_download_dir, f"bedrock-server-{self.actual_version}.zip"
        )

        # Download the file only if it doesn't already exist.
        if not os.path.exists(self.zip_file_path):
            self.logger.info(
                f"Server version {self.actual_version} ZIP not found locally. Downloading..."
            )
            self._download_server_zip_file()
        else:
            self.logger.info(
                f"Server version {self.actual_version} ZIP already exists at '{self.zip_file_path}'. Skipping download."
            )

        # Prune the cache after a potential download.
        self._execute_instance_pruning()
        self.logger.info(
            f"Download preparation completed for version {self.actual_version}."
        )

        if (
            not self.actual_version
            or not self.zip_file_path
            or not self.specific_download_dir
        ):
            raise DownloadError("Critical state missing after download preparation.")
        return self.actual_version, self.zip_file_path, self.specific_download_dir

    def extract_server_files(self, is_update: bool):
        """Extracts server files from the downloaded ZIP to the target server directory.

        This method assumes that :meth:`.prepare_download_assets()` has been
        successfully called, so that ``self.zip_file_path`` points to a valid
        local ZIP file and ``self.server_dir`` is the target extraction directory.

        The behavior changes based on the `is_update` flag:

            - If `is_update` is ``True``, extraction preserves specific files and
              directories listed in :attr:`.PRESERVED_ITEMS_ON_UPDATE` (e.g., worlds,
              server.properties, allowlist.json, permissions.json). Other files
              from the ZIP archive will overwrite existing files.
            - If `is_update` is ``False`` (fresh install), all files from the ZIP
              archive are extracted, potentially overwriting anything in the
              ``self.server_dir``.

        Args:
            is_update (bool): If ``True``, performs an update extraction, preserving
                key server files and data. If ``False``, performs a fresh
                extraction of all files.

        Raises:
            MissingArgumentError: If ``self.zip_file_path`` is not set (i.e.,
                :meth:`.prepare_download_assets()` was likely not called).
            AppFileNotFoundError: If the ZIP file at ``self.zip_file_path``
                does not exist.
            FileOperationError: If creating the ``self.server_dir`` fails or if
                there are other filesystem errors during extraction (e.g., permissions).
            ExtractError: If the ZIP file is invalid, corrupted, or if an
                unexpected error occurs during the extraction process.
        """
        if not self.zip_file_path:
            raise MissingArgumentError(
                "ZIP file path not set. Call prepare_download_assets() first."
            )
        if not os.path.exists(self.zip_file_path):
            raise AppFileNotFoundError(self.zip_file_path, "ZIP file to extract")

        self.logger.info(
            f"Extracting server files from '{self.zip_file_path}' to '{self.server_dir}'..."
        )
        self.logger.debug(
            f"Extraction mode: {'Update (preserving config/worlds)' if is_update else 'Fresh install'}"
        )

        try:
            os.makedirs(self.server_dir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Cannot create target directory '{self.server_dir}' for extraction: {e}"
            ) from e

        try:
            with zipfile.ZipFile(self.zip_file_path, "r") as zip_ref:
                # In update mode, skip preserved files.
                if is_update:
                    self.logger.debug(
                        f"Update mode: Excluding items matching: {self.PRESERVED_ITEMS_ON_UPDATE}"
                    )
                    extracted_count, skipped_count = 0, 0
                    for member in zip_ref.infolist():
                        member_path = member.filename.replace("\\", "/")
                        should_extract = not any(
                            member_path == item or member_path.startswith(item)
                            for item in self.PRESERVED_ITEMS_ON_UPDATE
                        )
                        if should_extract:
                            zip_ref.extract(member, path=self.server_dir)
                            extracted_count += 1
                        else:
                            self.logger.debug(
                                f"Skipping extraction of preserved item: {member_path}"
                            )
                            skipped_count += 1
                    self.logger.info(
                        f"Update extraction complete. Extracted {extracted_count} items, skipped {skipped_count} preserved items."
                    )
                # In fresh install mode, extract everything.
                else:
                    self.logger.debug("Fresh install mode: Extracting all files...")
                    zip_ref.extractall(self.server_dir)
                    self.logger.info(
                        f"Successfully extracted all files to: {self.server_dir}"
                    )
        except zipfile.BadZipFile as e:
            raise ExtractError(f"Invalid ZIP file: '{self.zip_file_path}'. {e}") from e
        except (OSError, IOError) as e:
            raise FileOperationError(f"Error during file extraction: {e}") from e
        except Exception as e:
            raise ExtractError(f"Unexpected error during extraction: {e}") from e

    def full_server_setup(self, is_update: bool) -> str:
        """Performs the complete server setup: download and extraction.

        This is a high-level convenience method that orchestrates the entire
        process of obtaining and setting up the Bedrock server files. It calls
        :meth:`.prepare_download_assets()` to handle the download (or use a
        cached version) and then calls :meth:`.extract_server_files()` to
        extract the archive into the target server directory.

        Args:
            is_update (bool): ``True`` if this is an update to an existing server
                (preserving data), ``False`` for a fresh installation. This flag
                is passed down to :meth:`.extract_server_files()`.

        Returns:
            str: The actual version string of the server that was successfully
            set up (e.g., "1.20.10.01").

        Raises:
            InternetConnectivityError: If internet is unavailable or download fails.
            FileOperationError: If directory/file operations fail during download or extraction.
            DownloadError: If version/URL resolution or download preparation fails.
            ExtractError: If the server archive extraction fails.
            SystemError: If the OS is unsupported.
            MissingArgumentError: If prerequisites for extraction are not met.
            AppFileNotFoundError: If the ZIP file is missing before extraction.
        """
        self.logger.info(
            f"Starting full server setup for '{self.server_dir}', version '{self.input_target_version}', update={is_update}"
        )
        actual_version, _, _ = self.prepare_download_assets()
        self.extract_server_files(is_update)
        self.logger.info(
            f"Server setup/update for version {actual_version} completed in '{self.server_dir}'."
        )
        if not actual_version:
            raise DownloadError("Actual version not determined after full setup.")
        return actual_version

    def get_actual_version(self) -> Optional[str]:
        """Returns the resolved actual version string of the server.

        This value is populated after :meth:`.get_version_for_target_spec` or
        :meth:`.prepare_download_assets` has been successfully called.

        Returns:
            Optional[str]: The actual version string (e.g., "1.20.10.01"),
            or ``None`` if the version has not been resolved yet.
        """
        return self.actual_version

    def get_zip_file_path(self) -> Optional[str]:
        """Returns the absolute path to the downloaded (or identified) server ZIP file.

        This value is populated after :meth:`.prepare_download_assets` has
        successfully identified or downloaded the ZIP file.

        Returns:
            Optional[str]: The full path to the server ZIP file, or ``None`` if
            not yet determined.
        """
        return self.zip_file_path

    def get_specific_download_dir(self) -> Optional[str]:
        """Returns the specific download directory used for this instance's downloads.

        This is typically a subdirectory like 'stable' or 'preview' within the
        main download directory. It's populated by :meth:`.prepare_download_assets`.

        Returns:
            Optional[str]: The absolute path to the instance's specific download
            directory (e.g., ``/path/to/downloads/stable``), or ``None`` if not
            yet determined.
        """
        return self.specific_download_dir

    def get_resolved_download_url(self) -> Optional[str]:
        """Returns the fully resolved download URL for the server archive.

        This value is populated after :meth:`.get_version_for_target_spec` or
        :meth:`.prepare_download_assets` (which calls the former) has successfully
        resolved the URL.

        Returns:
            Optional[str]: The complete download URL, or ``None`` if not yet resolved.
        """
        return self.resolved_download_url
