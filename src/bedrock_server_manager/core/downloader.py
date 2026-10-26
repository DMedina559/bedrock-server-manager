# bedrock_server_manager/core/downloader.py
"""Resolve Bedrock downloads, prepare server files and prune cached archives."""

import asyncio
import json
import logging
import os
import platform
import re
import threading
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Set, Tuple

import aiofiles
import aiofiles.os
import aiofiles.ospath
import aiohttp

from ..error import (
    AppFileNotFoundError,
    ConfigurationError,
    DownloadError,
    ExtractError,
    FileOperationError,
    InternetConnectivityError,
    MissingArgumentError,
    SystemError,
    UserInputError,
)
from ..failures import classify_failure
from ..results import CleanupResult
from ..utils.threads import run_in_thread
from .files import (
    extract_archive,
    file_transaction,
    temporary_directory,
    validate_archive,
)
from .system import base as system_base
from .system import find_files

if TYPE_CHECKING:
    from ..config.settings import Settings

logger = logging.getLogger(__name__)


async def prune_old_downloads(download_dir: str, download_keep: int) -> CleanupResult:
    """Report every retention deletion rather than hiding filesystem failures."""
    if not download_dir:
        raise MissingArgumentError("Download directory is required.")
    if (
        isinstance(download_keep, bool)
        or not isinstance(download_keep, int)
        or download_keep < 0
    ):
        raise UserInputError("Download retention must be a non-negative integer.")
    if not await aiofiles.ospath.isdir(download_dir):
        return CleanupResult()
    try:
        files = await find_files(
            download_dir, "bedrock-server-*.zip", sort_by="mtime", reverse=True
        )
        paths = [str(path) for path in files if isinstance(path, str)]
    except OSError as error:
        raise FileOperationError("Cannot list download cache.") from error
    deleted = []
    failures = {}
    for path in paths[download_keep:]:
        try:
            await run_in_thread(os.remove, path)
            deleted.append(path)
        except OSError as error:
            failures[path] = classify_failure(error).error
    return CleanupResult(
        deleted=deleted, retained=paths[:download_keep], failures=failures
    )


class BedrockDownloader:
    """Prepare Bedrock files for a release target or a custom archive.

    Supported targets are stable, preview, explicit versions and ``CUSTOM``.
    """

    PRESERVED_ITEMS_ON_UPDATE: Set[str] = {
        "worlds/",
        "allowlist.json",
        "permissions.json",
        "server.properties",
    }

    server_zip_path: str | None

    def __init__(
        self,
        settings_obj: "Settings",
        server_dir: str,
        target_version: str = "LATEST",
        server_zip_path: Optional[str] = None,
    ):
        """Bind settings, destination and version target for a server download.

        ``CUSTOM`` requires ``server_zip_path``; download paths come from settings.
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
        """Resolve stable, preview and explicit version selectors into instance fields."""
        target_upper = self.input_target_version.upper()
        if target_upper == "CUSTOM":
            self._version_type = "CUSTOM"
            self.logger.debug(
                "Instance targeting CUSTOM version for server: %s", self.server_dir
            )
        elif target_upper == "PREVIEW":
            self._version_type = "PREVIEW"
            self.logger.debug(
                "Instance targeting latest PREVIEW version for server: %s",
                self.server_dir,
            )
        elif target_upper == "LATEST":
            self._version_type = "LATEST"
            self.logger.debug(
                "Instance targeting latest STABLE version for server: %s",
                self.server_dir,
            )
        elif target_upper.endswith("-PREVIEW"):
            self._version_type = "PREVIEW"
            self._custom_version_number = self.input_target_version[: -len("-PREVIEW")]
            self.logger.debug(
                "Instance targeting specific PREVIEW version '%s' for server: %s",
                self._custom_version_number,
                self.server_dir,
            )
        else:
            self._version_type = "LATEST"  # Assume a specific stable version
            self._custom_version_number = self.input_target_version
            self.logger.debug(
                "Instance targeting specific STABLE version '%s' for server: %s",
                self._custom_version_number,
                self.server_dir,
            )

    async def _lookup_bedrock_download_url(self) -> str:  # noqa: C901
        """Resolve the requested release URL through the Bedrock download API.

        Connectivity and invalid-response failures propagate as application
        exceptions.
        """
        self.logger.debug(
            "Asynchronously looking up download URL for target: '%s'",
            self.input_target_version,
        )
        API_URL = self.settings.get(
            "downloader.download_url",
            "https://net-secondary.web.minecraft-services.net/api/v1.0/download/links",
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
        self.logger.debug("Targeting API downloadType identifier: '%s'", download_type)

        # 2. Fetch data from the API asynchronously.
        try:

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(
                timeout=timeout, headers=headers
            ) as session:
                async with session.get(API_URL) as response:
                    response.raise_for_status()
                    api_data = await response.json(content_type=None)
            self.logger.debug("Bedrock release metadata retrieved.")
        except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError) as e:
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
                "API response did not contain a URL for downloadType '%s'.",
                download_type,
            )
            raise DownloadError(
                f"The API did not provide a download URL for your system ({download_type})."
            )
        self.logger.debug("Found URL via API for '%s': %s", download_type, base_url)

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
                self.resolved_download_url = str(modified_url)
                self.logger.debug(
                    "Constructed specific version URL: %s", self.resolved_download_url
                )
                return str(modified_url)
            except Exception as e:
                raise DownloadError(
                    f"Error modifying URL for specific version '{self._custom_version_number}': {e}"
                ) from e
        else:
            self.resolved_download_url = str(base_url)
            return str(base_url)

    def _get_version_from_url(self) -> str:
        """Extracts the version number from the resolved download URL or custom zip path.
        This method populates ``self.actual_version``.
        :returns: The extracted version string (e.g., "1.20.10.01").

        :raises MissingArgumentError: If the download URL has not been resolved yet.
        :raises DownloadError: If the URL format is unexpected and the version
            cannot be parsed."""
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
                "Extracted version '%s' from standard path format: %s",
                version,
                source_path,
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
                    "Extracted version '%s' from custom ZIP name: %s",
                    version,
                    source_path,
                )
                self.actual_version = version
                return self.actual_version
            else:
                # Fallback for custom zips that don't have a clear version number
                custom_version = Path(source_path).stem
                self.logger.warning(
                    "Could not parse a version number from custom ZIP '%s'. Using filename stem '%s' as version.",
                    source_path,
                    custom_version,
                )
                self.actual_version = custom_version
                return self.actual_version

        # If it's not a custom zip and didn't match the standard format, it's an error
        raise DownloadError(
            f"Failed to extract version number from URL format: {source_path}"
        )

    async def _download_server_zip_file(self):  # noqa: C901
        """Asynchronously downloads the server ZIP file from the resolved URL.

        :raises MissingArgumentError: If the URL or target file path are not set.
        :raises FileOperationError: If directories cannot be created or the file
            cannot be written.
        :raises InternetConnectivityError: If the download request fails."""
        if not self.resolved_download_url or not self.zip_file_path:
            raise MissingArgumentError(
                "Download URL or ZIP file path not set. Cannot download."
            )

        self.logger.debug(
            "Attempting to download server from: %s", self.resolved_download_url
        )
        self.logger.debug("Saving downloaded file to: %s", self.zip_file_path)

        target_dir = os.path.dirname(self.zip_file_path)
        try:
            if target_dir and not await aiofiles.ospath.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Cannot create directory '{target_dir}' for download: {e}"
            ) from e

        try:
            async with temporary_directory(target_dir or ".") as staging:
                download_path = staging / "download.zip"

                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                # Use a streaming request to handle large files efficiently.
                timeout = aiohttp.ClientTimeout(total=600, connect=30, sock_read=60)
                async with aiohttp.ClientSession(
                    timeout=timeout, headers=headers
                ) as session:
                    async with session.get(self.resolved_download_url) as response:
                        response.raise_for_status()
                        self.logger.debug(
                            "Download request successful (status %s). Writing to file.",
                            response.status,
                        )
                        total_size = int(response.headers.get("content-length", 0))
                        bytes_written = 0
                        async with aiofiles.open(download_path, "wb") as f:
                            # Write the file in chunks to avoid high memory usage.
                            async for chunk in response.content.iter_chunked(8192 * 4):
                                await f.write(chunk)
                                bytes_written += len(chunk)
                        self.logger.info(
                            "Bedrock download complete (%s bytes): '%s'.",
                            bytes_written,
                            self.zip_file_path,
                        )
                        if total_size != 0 and bytes_written != total_size:
                            raise InternetConnectivityError(
                                f"Downloaded size ({bytes_written}) does not match content-length ({total_size}). File might be incomplete."
                            )

                def validate() -> None:
                    with zipfile.ZipFile(download_path) as archive:
                        validate_archive(archive)
                        bad = archive.testzip()
                        if bad is not None:
                            raise zipfile.BadZipFile(f"Corrupt archive entry: {bad}")

                await run_in_thread(validate)
                await run_in_thread(os.replace, download_path, self.zip_file_path)
        except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError) as e:
            raise InternetConnectivityError(
                f"Download failed for '{self.resolved_download_url}': {e}"
            ) from e
        except InternetConnectivityError:
            raise
        except OSError as e:
            raise FileOperationError(
                f"Cannot write to file '{self.zip_file_path}': {e}"
            ) from e
        except Exception as e:
            raise FileOperationError(f"Unexpected error during download: {e}") from e

    async def _execute_instance_pruning(self):
        """Prune the selected download cache using the configured retention count.

        Pruning failures are logged without interrupting installation.
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
                    "Invalid DOWNLOAD_KEEP setting ('%s'). Must be >= 0. Skipping.",
                    keep_setting,
                )
                return
            self.logger.debug(
                "Instance triggering pruning for '%s' keeping %s files.",
                self.specific_download_dir,
                effective_keep,
            )
            result = await prune_old_downloads(
                self.specific_download_dir, effective_keep
            )
            if result.failures:
                self.logger.warning(
                    "Download retention failed for %s cached archives.",
                    len(result.failures),
                )
        except (
            UserInputError,
            FileOperationError,
            AppFileNotFoundError,
            MissingArgumentError,
            Exception,
        ) as e:
            # Log as a warning and continue, as pruning failure should not block the main operation.
            self.logger.warning(
                "Pruning failed for instance's directory '%s': %s. Continuing main operation.",
                self.specific_download_dir,
                e,
                exc_info=True,
            )

    def _update_server_properties_from_zip(
        self, zip_ref: zipfile.ZipFile, target_dir: Path | None = None
    ) -> None:
        """Updates the server.properties file by applying existing user values
        on top of the fresh file from the zip archive.

        :param zip_ref: The opened ZIP file containing the new server files.
        """
        server_properties_path = os.path.join(self.server_dir, "server.properties")

        if not os.path.exists(server_properties_path):
            return

        if "server.properties" not in zip_ref.namelist():
            return

        # 1. Read existing properties (user's custom settings)
        user_properties = {}
        try:
            with open(server_properties_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    parts = stripped.split("=", 1)
                    if len(parts) == 2 and parts[0].strip():
                        user_properties[parts[0].strip()] = parts[1].strip()
        except OSError as e:
            self.logger.warning(
                "Could not read existing server.properties to merge new properties: %s",
                e,
            )
            raise

        # 2. Extract properties from zip and merge
        try:
            merged_lines = []
            keys_in_new_file = set()
            with zip_ref.open("server.properties") as zf:
                for line_bytes in zf:
                    decoded_line = line_bytes.decode("utf-8").rstrip("\r\n")
                    stripped = decoded_line.strip()

                    if not stripped or stripped.startswith("#"):
                        merged_lines.append(decoded_line)
                        continue

                    parts = stripped.split("=", 1)
                    if len(parts) == 2 and parts[0].strip():
                        key = parts[0].strip()
                        keys_in_new_file.add(key)

                        # If user has this property, use their value
                        if key in user_properties:
                            merged_lines.append(f"{key}={user_properties[key]}")
                        else:
                            # Use default from zip
                            merged_lines.append(decoded_line)
                    else:
                        merged_lines.append(decoded_line)

            # 3. Find legacy or custom properties that are not in the new file
            legacy_keys = [k for k in user_properties if k not in keys_in_new_file]
            if legacy_keys:
                merged_lines.append("")
                merged_lines.append("# Legacy or custom properties")
                for k in legacy_keys:
                    merged_lines.append(f"{k}={user_properties[k]}")

            # 4. Write back out to disk
            with open(
                (
                    (target_dir / "server.properties")
                    if target_dir
                    else server_properties_path
                ),
                "w",
                encoding="utf-8",
            ) as f:
                f.write("\n".join(merged_lines) + "\n")

            self.logger.debug(
                "Successfully merged user values into new server.properties"
            )

        except Exception as e:
            self.logger.warning("Could not merge new server.properties from zip: %s", e)
            raise

    def get_actual_version(self) -> Optional[str]:
        """Return the resolved actual version string of the server.

        This value is populated after :meth:`.get_version_for_target_spec` or
        :meth:`.prepare_download_assets` has been successfully called.

        :returns: The actual version string (e.g., "1.20.10.01"),
                  or ``None`` if the version has not been resolved yet.
        """
        return self.actual_version

    def get_zip_file_path(self) -> Optional[str]:
        """Return the absolute path to the downloaded (or identified) server ZIP file.

        This value is populated after :meth:`.prepare_download_assets` has
        successfully identified or downloaded the ZIP file.

        :returns: The full path to the server ZIP file, or ``None`` if
                  not yet determined.
        """
        return self.zip_file_path

    def get_specific_download_dir(self) -> Optional[str]:
        """Return the selected cache directory, or ``None`` before preparation."""
        return self.specific_download_dir

    def get_resolved_download_url(self) -> Optional[str]:
        """Return the fully resolved download URL for the server archive.

        This value is populated after :meth:`.get_version_for_target_spec` or
        :meth:`.prepare_download_assets` (which calls the former) has successfully
        resolved the URL.

        :returns: The complete download URL, or ``None`` if not yet resolved.
        """
        return self.resolved_download_url

    async def extract_server_files(self, is_update: bool):
        """Extracts server files asynchronously."""
        if not self.zip_file_path:
            raise MissingArgumentError(
                "ZIP file path not set. Call prepare_download_assets() first."
            )
        if not await aiofiles.ospath.exists(self.zip_file_path):
            raise AppFileNotFoundError(self.zip_file_path, "ZIP file to extract")

        self.logger.info("Extracting Bedrock server files into '%s'.", self.server_dir)
        self.logger.debug(
            "Extraction mode: %s",
            "Update (preserving config/worlds)" if is_update else "Fresh install",
        )

        try:
            await run_in_thread(os.makedirs, self.server_dir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Cannot create target directory '{self.server_dir}' for extraction: {e}"
            ) from e

        try:
            async with temporary_directory(Path(self.server_dir).parent) as staging:

                archive_path = self.zip_file_path

                def prepare(cancellation_event: threading.Event | None = None) -> None:
                    with zipfile.ZipFile(archive_path, "r") as archive:
                        members = [
                            member
                            for member in archive.infolist()
                            if not is_update
                            or not any(
                                member.filename.replace("\\", "/") == item
                                or member.filename.replace("\\", "/").startswith(item)
                                for item in self.PRESERVED_ITEMS_ON_UPDATE
                            )
                        ]
                        extract_archive(archive, staging, members, cancellation_event)
                        if is_update:
                            self._update_server_properties_from_zip(archive, staging)

                await run_in_thread(prepare)
                async with file_transaction(
                    Path(self.server_dir).parent
                ) as transaction:

                    def install() -> None:
                        for entry in sorted(staging.rglob("*")):
                            target = Path(self.server_dir) / entry.relative_to(staging)
                            if entry.is_dir():
                                transaction.mkdir(target)
                            else:
                                transaction.replace(entry, target)

                    await run_in_thread(install)
        except zipfile.BadZipFile as error:
            raise ExtractError(
                f"Invalid ZIP file: '{self.zip_file_path}'. {error}"
            ) from error
        except OSError as error:
            raise FileOperationError(
                f"Error during file extraction: {error}"
            ) from error

    async def full_server_setup(self, is_update: bool) -> str:
        """Performs the complete server setup asynchronously."""
        self.logger.debug(
            "Starting full server setup for '%s', version '%s', update=%s",
            self.server_dir,
            self.input_target_version,
            is_update,
        )
        actual_version, _, _ = await self.prepare_download_assets()
        await self.extract_server_files(is_update)
        self.logger.debug(
            "Server setup/update for version %s completed in '%s'.",
            actual_version,
            self.server_dir,
        )
        if not actual_version:
            raise DownloadError("Actual version not determined after full setup.")
        return actual_version

    async def get_version_for_target_spec(self) -> str:
        """Resolves the target version asynchronously."""
        self.logger.debug(
            "Getting prospective version for target spec: '%s'",
            self.input_target_version,
        )
        if self._version_type == "CUSTOM":
            self.logger.debug("Custom version specified, skipping download URL lookup.")
            await run_in_thread(self._get_version_from_url)
        else:
            await self._lookup_bedrock_download_url()
            await run_in_thread(self._get_version_from_url)

        if not self.actual_version:
            raise DownloadError("Could not determine actual version from resolved URL.")
        return self.actual_version

    async def prepare_download_assets(self) -> Tuple[str, str, str]:
        """Prepares download assets asynchronously."""
        self.logger.debug(
            "Starting Bedrock server download preparation for directory: '%s'",
            self.server_dir,
        )

        if self._version_type == "CUSTOM":
            self.logger.debug(
                "Custom version specified. Using local ZIP: %s", self.server_zip_path
            )
            if not self.server_zip_path:
                raise MissingArgumentError(
                    "server_zip_path is required for CUSTOM version."
                )

            self.zip_file_path = self.server_zip_path
            await run_in_thread(self._get_version_from_url)

            self.specific_download_dir = str(Path(self.server_zip_path).parent)
            self.logger.debug(
                "Setting specific_download_dir for custom zip to: %s",
                self.specific_download_dir,
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

        await system_base.check_internet_connectivity()

        try:
            await run_in_thread(os.makedirs, self.server_dir, exist_ok=True)
            if self.base_download_dir:
                await run_in_thread(os.makedirs, self.base_download_dir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Failed to create required directories asynchronously: {e}"
            ) from e

        await self.get_version_for_target_spec()

        if (
            not self.actual_version
            or not self.resolved_download_url
            or not self.base_download_dir
        ):
            raise DownloadError(
                "Internal error: version or URL not resolved after lookup."
            )

        version_subdir_name = "preview" if self._version_type == "PREVIEW" else "stable"
        self.specific_download_dir = os.path.join(
            self.base_download_dir, version_subdir_name
        )
        self.logger.debug(
            "Using specific download subdirectory: %s", self.specific_download_dir
        )
        try:
            await run_in_thread(os.makedirs, self.specific_download_dir, exist_ok=True)
        except OSError as e:
            raise FileOperationError(
                f"Failed to create download subdirectory '{self.specific_download_dir}': {e}"
            ) from e

        self.zip_file_path = os.path.join(
            self.specific_download_dir, f"bedrock-server-{self.actual_version}.zip"
        )

        if not await aiofiles.ospath.exists(self.zip_file_path):
            self.logger.debug(
                "Server version %s ZIP not found locally. Downloading...",
                self.actual_version,
            )
            await self._download_server_zip_file()
        else:
            self.logger.debug(
                "Server version %s ZIP already exists at '%s'. Skipping download.",
                self.actual_version,
                self.zip_file_path,
            )

        await self._execute_instance_pruning()
        self.logger.debug(
            "Download preparation completed for version %s.", self.actual_version
        )

        if (
            not self.actual_version
            or not self.zip_file_path
            or not self.specific_download_dir
        ):
            raise DownloadError("Critical state missing after download preparation.")
        return self.actual_version, self.zip_file_path, self.specific_download_dir
