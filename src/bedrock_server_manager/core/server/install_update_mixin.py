# bedrock_server_manager/core/server/install_update_mixin.py
"""Provides the :class:`.ServerInstallUpdateMixin` for the :class:`~.core.bedrock_server.BedrockServer` class.

This mixin encapsulates the logic for installing new Bedrock server instances
and updating existing ones. It orchestrates the
:class:`~.core.downloader.BedrockDownloader` to fetch the correct server files
based on a version specification (e.g., "LATEST", "PREVIEW", or a specific
version number). It then manages the process of extracting these files into the
server's designated directory and applying necessary filesystem permissions.

Key functionalities include:

    - Checking if an update is needed by comparing the current installed version
      against a target version or dynamic specifier.
    - Performing the complete installation or update workflow, which involves:
        - Stopping the server if it's running.
        - Downloading the server software.
        - Extracting the archive (preserving user data on updates).
        - Setting filesystem permissions.
        - Updating the server's persisted version and status information.

"""
import os
import logging
from typing import Optional, Any

# Local application imports.
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.downloader import (
    BedrockDownloader,
)
from bedrock_server_manager.core.system import (
    base as system_base_utils,
)
from bedrock_server_manager.error import (
    MissingArgumentError,
    DownloadError,
    ExtractError,
    FileOperationError,
    PermissionsError,
    ServerStopError,
    AppFileNotFoundError,
    FileError,
    BSMError,
)


class ServerInstallUpdateMixin(BedrockServerBaseMixin):
    """Handles the installation and update procedures for a Bedrock server instance.

    This mixin extends :class:`.BedrockServerBaseMixin` and provides the core
    logic for acquiring and setting up Bedrock server software. It uses the
    :class:`~.core.downloader.BedrockDownloader` to manage the actual download
    and extraction of server files.

    Key responsibilities include:
        - Determining if an update is necessary by comparing the currently installed
          server version with a specified target version (which can be "LATEST",
          "PREVIEW", or a concrete version string).

        - Orchestrating the full install/update process:
            - Stopping the server if it's running (relies on :meth:`~.ServerProcessMixin.stop`).
            - Updating the server's persistent status (e.g., to "INSTALLING" or "UPDATING")
              (relies on :meth:`~.ServerStateMixin.set_status_in_config`).
            - Invoking the :class:`~.core.downloader.BedrockDownloader` to download
              and prepare server assets.
            - Extracting server files into the server directory, preserving user data
              (like worlds and properties) during updates.
            - Setting appropriate filesystem permissions on the server files
              (relies on a `set_filesystem_permissions` method, expected from another mixin
              or the main class).
            - Updating the server's persisted installed version and final status upon completion.
            - Cleaning up downloaded archive files.

    This mixin relies on several attributes initialized by :class:`.BedrockServerBaseMixin`
    (e.g., `server_name`, `server_dir`, `settings`, `logger`) and methods provided
    by other mixins that compose the final :class:`~.core.bedrock_server.BedrockServer`
    class (e.g., for checking installation status, getting/setting version, managing
    process state, and setting permissions).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes the ServerInstallUpdateMixin.

        Calls ``super().__init__(*args, **kwargs)`` to participate in cooperative
        multiple inheritance. It depends on attributes initialized by
        :class:`.BedrockServerBaseMixin` and assumes methods from other mixins
        (like :meth:`~.ServerStateMixin.set_status_in_config`,
        :meth:`~.ServerStateMixin.get_version`, :meth:`~.ServerProcessMixin.stop`, etc.)
        will be available on the composed ``BedrockServer`` object.

        Args:
            *args (Any): Variable length argument list passed to `super()`.
            **kwargs (Any): Arbitrary keyword arguments passed to `super()`.
        """
        super().__init__(*args, **kwargs)
        # Dependencies on other mixins' methods are resolved at runtime on the
        # final BedrockServer class instance.

    def _perform_server_files_setup(
        self, downloader: BedrockDownloader, is_update_operation: bool
    ) -> None:
        """Core helper to extract server files and set filesystem permissions.

        This internal method is called by :meth:`.install_or_update` after server
        files have been successfully downloaded by the `downloader`. It first
        delegates to :meth:`BedrockDownloader.extract_server_files` to extract
        the archive into the server directory, respecting the `is_update_operation`
        flag to preserve user data if applicable.

        After extraction, it calls ``self.set_filesystem_permissions()`` (a method
        expected to be provided by another mixin or the main class, likely from
        a permissions-focused mixin that uses :func:`~.core.system.base.set_server_folder_permissions`)
        to apply appropriate permissions to the newly extracted files and folders.

        Args:
            downloader (BedrockDownloader): An initialized and prepared
                :class:`~.core.downloader.BedrockDownloader` instance that has
                already downloaded the server files. Its ``get_zip_file_path()``
                method will be used.
            is_update_operation (bool): ``True`` if this is an update to an existing
                installation (which preserves certain files during extraction),
                ``False`` for a fresh installation.

        Raises:
            ExtractError: If the file extraction process fails (propagated from
                ``downloader.extract_server_files``).
            PermissionsError: If setting filesystem permissions fails (propagated
                from ``self.set_filesystem_permissions()``).
            AttributeError: If ``self.set_filesystem_permissions()`` method is not
                available on the instance (indicating a missing mixin).
        """
        zip_file_path_str = downloader.get_zip_file_path()
        if not zip_file_path_str:  # Should not happen if downloader is prepared
            raise ExtractError(
                "Downloader did not provide a valid ZIP file path for extraction."
            )
        zip_file_basename = os.path.basename(zip_file_path_str)

        self.logger.info(
            f"Server '{self.server_name}': Setting up server files in '{self.server_dir}' from '{zip_file_basename}'. Update: {is_update_operation}"
        )
        try:
            # Delegate the extraction logic to the downloader.
            downloader.extract_server_files(is_update_operation)
            self.logger.info(
                f"Server file extraction completed for '{self.server_name}'."
            )
        except (
            FileError,
            MissingArgumentError,
            AppFileNotFoundError,
            ExtractError,
        ) as e_extract:  # Catch specific errors from downloader
            raise ExtractError(
                f"Extraction phase failed for server '{self.server_name}': {e_extract}"
            ) from e_extract

        try:
            # Set filesystem permissions after extraction.
            # This relies on set_filesystem_permissions being mixed in from elsewhere.
            if not hasattr(self, "set_filesystem_permissions"):
                self.logger.error(
                    "set_filesystem_permissions method not found on server instance. Cannot set permissions."
                )
                # Decide if this is fatal. For now, let it proceed but it's a setup issue.
                raise AttributeError(
                    "Server instance is missing 'set_filesystem_permissions' method."
                )

            self.logger.debug(
                f"Setting permissions for server directory: {self.server_dir}"
            )
            self.set_filesystem_permissions()  # type: ignore
            self.logger.debug(
                f"Server folder permissions set for '{self.server_name}'."
            )
        except PermissionsError:  # Re-raise PermissionsError directly
            raise
        except Exception as e_perm:  # Wrap other unexpected permission errors
            self.logger.error(
                f"Failed to set permissions for '{self.server_dir}' during setup: {e_perm}. Installation may be incomplete."
            )
            raise PermissionsError(
                f"Unexpected error setting permissions for '{self.server_dir}'."
            ) from e_perm

    def is_update_needed(self, target_version_specification: str) -> bool:
        """Checks if the server's installed version requires an update to meet the target.

        This method compares the server's currently installed version (obtained via
        ``self.get_version()``, expected from :class:`.ServerStateMixin`) against the
        `target_version_specification`. The target can be:

            - A specific version string (e.g., "1.20.10.01").
            - "LATEST" (for the latest stable release).
            - "PREVIEW" (for the latest preview release).

        If the target is "LATEST" or "PREVIEW", this method uses
        :class:`~.core.downloader.BedrockDownloader` to fetch the actual latest
        version number corresponding to that specification for comparison.
        If the target is a specific version, it's compared directly.

        Args:
            target_version_specification (str): The target version to check against
                (e.g., "1.20.10.01", "LATEST", "PREVIEW").

        Returns:
            bool: ``True`` if an update is determined to be needed, ``False`` otherwise.
            Returns ``True`` as a fail-safe if the current version is "UNKNOWN" or if
            there are errors fetching remote version information for "LATEST"/"PREVIEW".

        Raises:
            MissingArgumentError: If `target_version_specification` is empty or not a string.
            AttributeError: If ``self.get_version()`` method is not available.
        """
        if (
            not isinstance(target_version_specification, str)
            or not target_version_specification
        ):
            raise MissingArgumentError(
                "Target version specification cannot be empty and must be a string."
            )

        if not hasattr(self, "get_version"):
            self.logger.error(
                "get_version method not found on server instance. Cannot check if update is needed."
            )
            raise AttributeError("Server instance is missing 'get_version' method.")

        current_installed_version: str = self.get_version()  # type: ignore
        target_spec_upper = target_version_specification.strip().upper()
        is_latest_or_preview = target_spec_upper in ("LATEST", "PREVIEW")

        # --- Path 1: Target is a specific version string ---
        if not is_latest_or_preview:
            # For a specific target version, we need to normalize it if it includes "-PREVIEW"
            # The BedrockDownloader's _custom_version_number handles this normalization.
            try:
                temp_downloader_for_parse = BedrockDownloader(
                    settings_obj=self.settings,  # Assumes self.settings is available
                    server_dir=self.server_dir,  # Assumes self.server_dir is available
                    target_version=target_version_specification,
                )
                # _custom_version_number will be the numeric part, e.g., "1.20.10.01"
                # even if input was "1.20.10.01-PREVIEW" (type is handled by _version_type)
                specific_target_numeric = (
                    temp_downloader_for_parse._custom_version_number
                )

                if (
                    not specific_target_numeric
                ):  # Should not happen if BedrockDownloader parses correctly
                    self.logger.warning(
                        f"Could not parse numeric version from specific target '{target_version_specification}'. Assuming update needed as a precaution."
                    )
                    return True

                if current_installed_version == specific_target_numeric:
                    self.logger.info(
                        f"Server '{self.server_name}' (v{current_installed_version}) matches specific target '{target_version_specification}'. No update needed."
                    )
                    return False
                else:
                    self.logger.info(
                        f"Server '{self.server_name}' (v{current_installed_version}) differs from specific target '{target_version_specification}' (parsed as {specific_target_numeric}). Update needed."
                    )
                    return True
            except (
                BSMError
            ) as e_parse:  # Catch known BSM errors from BedrockDownloader init
                self.logger.warning(
                    f"Error initializing downloader for parsing specific target version '{target_version_specification}': {e_parse}. Assuming update needed.",
                    exc_info=True,
                )
                return True
            except Exception as e_unexp_parse:  # Catch any other unexpected error
                self.logger.error(
                    f"Unexpected error parsing specific target version '{target_version_specification}': {e_unexp_parse}. Assuming update needed.",
                    exc_info=True,
                )
                return True

        # --- Path 2: Target is "LATEST" or "PREVIEW" ---
        if (
            not current_installed_version
            or current_installed_version.upper() == "UNKNOWN"
        ):
            self.logger.info(
                f"Server '{self.server_name}' has version '{current_installed_version}'. Update to '{target_spec_upper}' is needed."
            )
            return True

        self.logger.debug(
            f"Server '{self.server_name}': Checking update. Installed='{current_installed_version}', Target='{target_spec_upper}'."
        )
        try:
            # This requires a network call to get the latest version info.
            downloader = BedrockDownloader(
                settings_obj=self.settings,
                server_dir=self.server_dir,  # Used by downloader for context, though not for file ops here
                target_version=target_spec_upper,  # "LATEST" or "PREVIEW"
            )
            latest_available_for_spec = downloader.get_version_for_target_spec()

            if current_installed_version == latest_available_for_spec:
                self.logger.info(
                    f"Server '{self.server_name}' (v{current_installed_version}) is up-to-date with '{target_spec_upper}' (which is v{latest_available_for_spec}). No update needed."
                )
                return False
            else:
                self.logger.info(
                    f"Server '{self.server_name}' (v{current_installed_version}) needs update. Target '{target_spec_upper}' is currently v{latest_available_for_spec}."
                )
                return True
        except (
            BSMError
        ) as e_fetch:  # Catch specific BSM errors like NetworkError, DownloadError
            self.logger.warning(
                f"Could not get latest version for '{target_spec_upper}' due to: {e_fetch}. Assuming update might be needed as a precaution.",
                exc_info=True,  # Log traceback for BSMError for better debugging
            )
            return True
        except Exception as e_unexp_fetch:  # Catch any other unexpected error
            self.logger.error(
                f"Unexpected error checking update for '{self.server_name}' against '{target_spec_upper}': {e_unexp_fetch}",
                exc_info=True,
            )
            return True  # Fail-safe: assume update needed

    def install_or_update(
        self, target_version_specification: str, force_reinstall: bool = False
    ) -> None:
        """Installs or updates the Bedrock server to a specified version or dynamic target.

        This is the primary method for managing server software versions. It
        orchestrates the entire workflow:

            1. Checks if an update is needed using :meth:`.is_update_needed` (unless
               `force_reinstall` is ``True`` or the server isn't installed).
            2. If the server is running, stops it using ``self.stop()`` (expected from
               :class:`~.ServerProcessMixin`).
            3. Updates the server's persisted status to "INSTALLING" or "UPDATING"
               (via ``self.set_status_in_config()`` from :class:`.ServerStateMixin`).
            4. If it's a new installation, sets the target version in the config.
            5. Initializes a :class:`~.core.downloader.BedrockDownloader` for the
               `target_version_specification`.
            6. Calls :meth:`BedrockDownloader.prepare_download_assets` to download/verify files.
            7. Calls the internal helper :meth:`._perform_server_files_setup` to extract
               the archive and set permissions. This helper, in turn, relies on
               ``self.set_filesystem_permissions()`` (expected from another mixin).
            8. Updates the server's persisted installed version (via ``self.set_version()``
               from :class:`.ServerStateMixin`) and final status ("INSTALLED" or "UPDATED").
            9. Cleans up the downloaded ZIP archive.

        Args:
            target_version_specification (str): The target version to install or
                update to. Can be a specific version string (e.g., "1.20.10.01"),
                "LATEST" (for the latest stable release), or "PREVIEW" (for the
                latest preview release).
            force_reinstall (bool, optional): If ``True``, the server software will
                be reinstalled/extracted even if :meth:`.is_update_needed` reports
                that the current version matches the target. Defaults to ``False``.

        Raises:
            MissingArgumentError: If `target_version_specification` is empty.
            ServerStopError: If the server is running and fails to stop.
            DownloadError: If the server software download fails.
            ExtractError: If the downloaded server archive cannot be extracted.
            PermissionsError: If filesystem permissions cannot be set after extraction.
            FileOperationError: For other unexpected file I/O errors during the process.
            AttributeError: If essential methods from other mixins (like `is_installed`,
                `stop`, `set_status_in_config`, `set_version`, `set_filesystem_permissions`)
                are not available on the instance.
            BSMError: For other known application-specific errors during the process.
        """
        if (
            not isinstance(target_version_specification, str)
            or not target_version_specification
        ):
            raise MissingArgumentError(
                "Target version specification cannot be empty and must be a string."
            )

        self.logger.info(
            f"Server '{self.server_name}': Initiating install/update to version spec '{target_version_specification}'. Force reinstall: {force_reinstall}"
        )

        # Check for required methods from other mixins
        required_methods = [
            "is_installed",
            "is_running",
            "stop",
            "set_status_in_config",
            "set_target_version",
            "set_version",
            "set_filesystem_permissions",
        ]
        for method_name in required_methods:
            if not hasattr(self, method_name):
                raise AttributeError(
                    f"ServerInstallUpdateMixin on '{self.server_name}' requires method '{method_name}' which is missing. Ensure all necessary mixins are included."
                )

        is_currently_installed: bool = self.is_installed()  # type: ignore

        if not force_reinstall and is_currently_installed:
            if not self.is_update_needed(
                target_version_specification
            ):  # Already checks target_version_specification
                self.logger.info(
                    f"Server '{self.server_name}' is already at the target version or latest for '{target_version_specification}'. No action taken."
                )
                return

        if self.is_running():  # type: ignore
            self.logger.info(
                f"Server '{self.server_name}' is running. Stopping before install/update."
            )
            try:
                self.stop()  # type: ignore
            except ServerStopError:  # Let ServerStopError propagate
                raise
            except Exception as e_stop:  # Wrap other errors from stop()
                raise ServerStopError(
                    f"Failed to stop server '{self.server_name}' before install/update: {e_stop}"
                ) from e_stop

        status_to_set = "UPDATING" if is_currently_installed else "INSTALLING"
        try:
            self.set_status_in_config(status_to_set)  # type: ignore
        except Exception as e_stat:
            self.logger.warning(  # Non-fatal, proceed with install/update
                f"Could not set status to {status_to_set} for '{self.server_name}': {e_stat}"
            )

        try:
            if not is_currently_installed:  # Set target version only on initial install
                self.set_target_version(target_version_specification.strip().upper())  # type: ignore
        except Exception as e_set_target:
            self.logger.warning(
                f"Could not set target version for '{self.server_name}': {e_set_target}"
            )

        downloader = BedrockDownloader(
            settings_obj=self.settings,  # from BaseServerMixin
            server_dir=self.server_dir,  # from BaseServerMixin
            target_version=target_version_specification,
        )
        actual_version_downloaded: Optional[str] = None

        try:
            self.logger.info(
                f"Server '{self.server_name}': Preparing download assets for '{target_version_specification}'..."
            )
            # prepare_download_assets resolves the version and downloads if needed.
            actual_version_downloaded, _, _ = downloader.prepare_download_assets()
            if (
                not actual_version_downloaded
            ):  # Should be caught by prepare_download_assets itself
                raise DownloadError(
                    f"Could not resolve actual version number for spec '{target_version_specification}' after download preparation."
                )
            self.logger.info(
                f"Server '{self.server_name}': Assets prepared for version '{actual_version_downloaded}' (target spec: '{target_version_specification}')."
            )

            self.logger.info(
                f"Server '{self.server_name}': Setting up server files (extracting) for version '{actual_version_downloaded}'..."
            )
            # Determine if it's effectively an update (preserving files) or a fresh install (overwriting)
            is_update_op_for_extraction = is_currently_installed and not force_reinstall
            self._perform_server_files_setup(downloader, is_update_op_for_extraction)

            self.set_version(actual_version_downloaded)  # type: ignore
            self.set_status_in_config("UPDATED" if is_update_op_for_extraction else "INSTALLED")  # type: ignore
            self.logger.info(
                f"Server '{self.server_name}' successfully {'updated' if is_update_op_for_extraction else 'installed'} to version '{actual_version_downloaded}'."
            )

        except (
            BSMError
        ) as e_bsm_install:  # Catch known BSM errors from downloader or setup
            self.logger.error(
                f"Install/Update failed for server '{self.server_name}' due to a BSM error: {e_bsm_install}",
                exc_info=True,
            )
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("ERROR")  # type: ignore
            raise  # Re-raise specific, handled BSM errors.
        except Exception as e_unexp_install:  # Catch any other unexpected error
            self.logger.error(
                f"Unexpected error during install/update for '{self.server_name}': {e_unexp_install}",
                exc_info=True,
            )
            if hasattr(self, "set_status_in_config"):
                self.set_status_in_config("ERROR")  # type: ignore
            # Wrap in a generic FileOperationError if it's not already a BSMError
            raise FileOperationError(
                f"Unexpected failure during install/update for '{self.server_name}': {e_unexp_install}"
            ) from e_unexp_install
        finally:
            # Attempt to clean up the downloaded zip file, regardless of success/failure of install
            zip_path_to_clean = downloader.get_zip_file_path()
            if zip_path_to_clean and os.path.exists(zip_path_to_clean):
                try:
                    self.logger.debug(
                        f"Cleaning up downloaded ZIP: {zip_path_to_clean}"
                    )
                    os.remove(zip_path_to_clean)
                except OSError as e_clean:
                    self.logger.warning(
                        f"Failed to clean up downloaded ZIP '{zip_path_to_clean}': {e_clean}"
                    )
