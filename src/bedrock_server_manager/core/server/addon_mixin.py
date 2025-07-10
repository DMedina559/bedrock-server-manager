# bedrock_server_manager/core/server/addon_mixin.py
"""
Provides the :class:`.ServerAddonMixin` for the :class:`~.core.bedrock_server.BedrockServer` class.

This mixin encapsulates the logic for processing and managing server addons,
specifically ``.mcaddon`` and ``.mcpack`` files. Its responsibilities include:
    - Processing and extracting ``.mcaddon`` and ``.mcpack`` archives.
    - Parsing ``manifest.json`` files within addons to identify pack type, UUID, version, and name.
    - Installing behavior and resource packs into the server's active world directory.
    - Listing currently installed addons and their activation status.
    - Exporting installed addons back into ``.mcpack`` format.
    - Removing addons from a world, including deleting files and deactivating them.

It is designed to work in conjunction with other mixins of the
:class:`~.core.bedrock_server.BedrockServer`, primarily relying on:
    - :class:`~.core.server.state_mixin.ServerStateMixin` for methods like
      :meth:`~.core.server.state_mixin.ServerStateMixin.get_world_name` to determine
      the active world.
    - :class:`~.core.server.world_mixin.ServerWorldMixin` for methods like
      :meth:`~.core.server.world_mixin.ServerWorldMixin.extract_mcworld_to_directory`
      when processing ``.mcworld`` files found within ``.mcaddon`` archives.
"""
import os
import glob
import shutil
import zipfile
import tempfile
import json
import re
from typing import Tuple, List, Dict, Optional, Any

# Local application imports.
from .base_server_mixin import BedrockServerBaseMixin
from ...error import (
    MissingArgumentError,
    FileOperationError,
    UserInputError,
    ExtractError,
    AppFileNotFoundError,
    ConfigParseError,
)


class ServerAddonMixin(BedrockServerBaseMixin):
    """A mixin for the :class:`~.core.bedrock_server.BedrockServer` to manage server addons.

    This mixin provides a comprehensive suite of functionalities for handling
    Minecraft Bedrock Edition addons, typically distributed as ``.mcaddon`` or
    ``.mcpack`` files. Its primary responsibilities include:

        - Processing addon archives (``.mcaddon``, ``.mcpack``) by extracting their contents.
        - Parsing ``manifest.json`` files to retrieve addon metadata (type, UUID, version, name).
        - Installing behavior packs and resource packs into the active server world.
        - Listing all installed addons within a world, detailing their activation status
          (e.g., 'ACTIVE', 'INACTIVE', 'ORPHANED').
        - Exporting an installed addon back into a ``.mcpack`` file.
        - Removing an addon from a world, which involves deleting its files and
          deactivating it in the world's configuration.

    It inherits from :class:`.BedrockServerBaseMixin` to access common server
    attributes like ``server_name``, ``server_dir``, and ``logger``. It also
    relies on methods from other mixins that will be part of the composed
    :class:`~.core.bedrock_server.BedrockServer` class, such as
    :meth:`~.core.server.state_mixin.ServerStateMixin.get_world_name` and
    :meth:`~.core.server.world_mixin.ServerWorldMixin.extract_mcworld_to_directory`.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes the ServerAddonMixin.

        This constructor participates in Python's cooperative multiple inheritance
        by calling ``super().__init__(*args, **kwargs)``. It ensures that the
        initialization chain is correctly followed, allowing this mixin to
        rely on attributes (e.g., ``server_name``, ``server_dir``, ``logger`` from
        :class:`.BedrockServerBaseMixin`) and methods (e.g.,
        :meth:`~.core.server.state_mixin.ServerStateMixin.get_world_name` from
        :class:`~.core.server.state_mixin.ServerStateMixin`, or
        :meth:`~.core.server.world_mixin.ServerWorldMixin.extract_mcworld_to_directory`
        from :class:`~.core.server.world_mixin.ServerWorldMixin`) that are
        provided by other base or sibling mixins in the final
        :class:`~.core.bedrock_server.BedrockServer` class.

        Args:
            *args (Any): Variable length argument list passed to `super().__init__()`.
            **kwargs (Any): Arbitrary keyword arguments passed to `super().__init__()`.
        """
        super().__init__(*args, **kwargs)
        # This mixin depends on attributes from BaseMixin: self.server_name, self.base_dir, self.server_dir, self.logger.
        # It also depends on methods from other mixins that will be part of the final BedrockServer class, such as:
        # - self.get_world_name() (from StateMixin)
        # - self.extract_mcworld_to_directory() (from WorldMixin)

    def process_addon_file(self, addon_file_path: str) -> None:
        """Processes a given addon file (``.mcaddon`` or ``.mcpack``).

        This method acts as a high-level dispatcher. It inspects the file extension
        of the provided ``addon_file_path`` to determine if it's an ``.mcaddon``
        or ``.mcpack`` file. It then delegates the actual processing to the
        corresponding internal helper methods:
        :meth:`._process_mcaddon_archive` for ``.mcaddon`` files or
        :meth:`._process_mcpack_archive` for ``.mcpack`` files.

        Args:
            addon_file_path (str): The absolute path to the addon file
                (``.mcaddon`` or ``.mcpack``) to be processed.

        Raises:
            MissingArgumentError: If ``addon_file_path`` is empty or not provided.
            AppFileNotFoundError: If the file specified by ``addon_file_path``
                does not exist or is not a file.
            UserInputError: If the file extension is not ``.mcaddon`` or ``.mcpack``
                (case-insensitive).
        """
        if not addon_file_path:
            raise MissingArgumentError("Addon file path cannot be empty.")

        self.logger.info(
            f"Server '{self.server_name}': Processing addon file '{os.path.basename(addon_file_path)}'."
        )

        if not os.path.isfile(addon_file_path):
            raise AppFileNotFoundError(addon_file_path, "Addon file")

        addon_file_lower = addon_file_path.lower()
        if addon_file_lower.endswith(".mcaddon"):
            self.logger.debug("Detected .mcaddon file type. Delegating.")
            self._process_mcaddon_archive(addon_file_path)
        elif addon_file_lower.endswith(".mcpack"):
            self.logger.debug("Detected .mcpack file type. Delegating.")
            self._process_mcpack_archive(addon_file_path)
        else:
            err_msg = f"Unsupported addon file type: '{os.path.basename(addon_file_path)}'. Only .mcaddon and .mcpack are supported."
            self.logger.error(err_msg)
            raise UserInputError(err_msg)

    def _process_mcaddon_archive(self, mcaddon_file_path: str) -> None:
        """Extracts a ``.mcaddon`` archive and processes its contents.

        An ``.mcaddon`` file is a ZIP archive that can bundle multiple ``.mcpack``
        (behavior/resource packs) and potentially ``.mcworld`` (world template) files.
        This method handles the extraction of the ``.mcaddon`` archive into a
        temporary directory. It then delegates the processing of the extracted
        contents (individual ``.mcpack`` or ``.mcworld`` files) to
        :meth:`._process_extracted_mcaddon_contents`.

        The temporary directory is automatically cleaned up after processing,
        regardless of success or failure.

        Args:
            mcaddon_file_path (str): The absolute path to the ``.mcaddon`` file.

        Raises:
            ExtractError: If the ``.mcaddon`` file is not a valid ZIP archive
                (e.g., corrupted or wrong file type).
            FileOperationError: If an OS-level error occurs during the creation of
                the temporary directory, or during the extraction of the archive
                (e.g., due to permission issues or disk full).
        """
        self.logger.info(
            f"Server '{self.server_name}': Processing .mcaddon '{os.path.basename(mcaddon_file_path)}'."
        )

        # Use a temporary directory to handle the extraction.
        temp_dir = tempfile.mkdtemp(prefix=f"mcaddon_{self.server_name}_")
        self.logger.debug(
            f"Created temporary directory for .mcaddon extraction: {temp_dir}"
        )

        try:
            # Extract the archive.
            try:
                self.logger.info(
                    f"Extracting '{os.path.basename(mcaddon_file_path)}' to temp dir..."
                )
                with zipfile.ZipFile(mcaddon_file_path, "r") as zip_ref:
                    zip_ref.extractall(temp_dir)
                self.logger.debug(
                    f"Successfully extracted '{os.path.basename(mcaddon_file_path)}'."
                )
            except zipfile.BadZipFile as e:
                raise ExtractError(
                    f"Invalid .mcaddon (not a zip file): {os.path.basename(mcaddon_file_path)}"
                ) from e
            except OSError as e:
                raise FileOperationError(
                    f"OS error extracting '{os.path.basename(mcaddon_file_path)}': {e}"
                ) from e

            # Delegate to process the extracted contents.
            self._process_extracted_mcaddon_contents(temp_dir)

        finally:
            # Ensure the temporary directory is cleaned up.
            if os.path.isdir(temp_dir):
                try:
                    self.logger.debug(f"Cleaning up temp directory: {temp_dir}")
                    shutil.rmtree(temp_dir)
                except OSError as e:
                    self.logger.warning(
                        f"Could not remove temp directory '{temp_dir}': {e}",
                        exc_info=True,
                    )

    def _process_extracted_mcaddon_contents(
        self, temp_dir_with_extracted_files: str
    ) -> None:
        """Processes ``.mcworld`` and ``.mcpack`` files from an extracted ``.mcaddon`` archive.

        This method iterates through the files within the provided temporary directory
        (which contains the extracted contents of an ``.mcaddon`` file).
        It identifies and processes:

            - ``.mcworld`` files: These are processed by calling
              :meth:`~.core.server.world_mixin.ServerWorldMixin.extract_mcworld_to_directory`,
              effectively importing the world template into the server's active world.
              Requires :meth:`~.core.server.state_mixin.ServerStateMixin.get_world_name`
              to determine the active world.
            - ``.mcpack`` files: These are processed by recursively calling
              :meth:`._process_mcpack_archive` for each pack.

        Args:
            temp_dir_with_extracted_files (str): The absolute path to the
                temporary directory containing the extracted files from an
                ``.mcaddon`` archive.

        Raises:
            FileOperationError: If processing any of the contained ``.mcworld`` or
                ``.mcpack`` files fails. This can be due to issues raised by
                :meth:`~.core.server.world_mixin.ServerWorldMixin.extract_mcworld_to_directory`
                or :meth:`._process_mcpack_archive`.
            AttributeError: If required methods from other mixins, such as
                :meth:`~.core.server.state_mixin.ServerStateMixin.get_world_name` or
                :meth:`~.core.server.world_mixin.ServerWorldMixin.extract_mcworld_to_directory`,
                are not available on the server instance.
        """
        self.logger.debug(
            f"Server '{self.server_name}': Processing extracted .mcaddon contents in '{temp_dir_with_extracted_files}'."
        )

        # Process any .mcworld files found.
        mcworld_files_found = glob.glob(
            os.path.join(temp_dir_with_extracted_files, "*.mcworld")
        )
        if mcworld_files_found:
            self.logger.info(
                f"Found {len(mcworld_files_found)} .mcworld file(s) in .mcaddon."
            )
            # This method is expected to be on the final class from StateMixin.
            active_world_name = self.get_world_name()

            for world_file_path in mcworld_files_found:
                world_filename_basename = os.path.basename(world_file_path)
                self.logger.info(
                    f"Processing extracted world file: '{world_filename_basename}' into active world '{active_world_name}'."
                )
                try:
                    # This method is expected to be on the final class from WorldMixin.
                    self.extract_mcworld_to_directory(
                        world_file_path, active_world_name
                    )
                    self.logger.info(
                        f"Successfully processed '{world_filename_basename}' into world '{active_world_name}'."
                    )
                except Exception as e:
                    raise FileOperationError(
                        f"Failed processing world '{world_filename_basename}' from .mcaddon for server '{self.server_name}': {e}"
                    ) from e

        # Process any .mcpack files found.
        mcpack_files_found = glob.glob(
            os.path.join(temp_dir_with_extracted_files, "*.mcpack")
        )
        if mcpack_files_found:
            self.logger.info(
                f"Found {len(mcpack_files_found)} .mcpack file(s) in .mcaddon."
            )
            for pack_file_path in mcpack_files_found:
                pack_filename_basename = os.path.basename(pack_file_path)
                self.logger.info(
                    f"Processing extracted pack file: '{pack_filename_basename}'."
                )
                try:
                    # Recursively call the main pack processor.
                    self._process_mcpack_archive(pack_file_path)
                except Exception as e:
                    raise FileOperationError(
                        f"Failed processing pack '{pack_filename_basename}' from .mcaddon for server '{self.server_name}': {e}"
                    ) from e

        if not mcworld_files_found and not mcpack_files_found:
            self.logger.warning(
                f"No .mcworld or .mcpack files found in extracted .mcaddon at '{temp_dir_with_extracted_files}'."
            )

    def _process_mcpack_archive(self, mcpack_file_path: str) -> None:
        """Extracts a ``.mcpack`` archive and initiates its installation.

        An ``.mcpack`` file is typically a ZIP archive containing a single
        behavior or resource pack. This method performs the following steps:

            1. Extracts the contents of the ``.mcpack`` file into a temporary directory.
            2. Delegates the installation of the extracted pack data to
               :meth:`._install_pack_from_extracted_data`.

        The temporary directory is automatically cleaned up after processing.

        Args:
            mcpack_file_path (str): The absolute path to the ``.mcpack`` file.

        Raises:
            ExtractError: If the ``.mcpack`` file is not a valid ZIP archive.
            FileOperationError: If an OS-level error occurs during temporary
                directory creation or archive extraction (e.g., permission issues,
                disk full).

            # Note: Further errors can be raised by _install_pack_from_extracted_data
        """
        mcpack_filename = os.path.basename(mcpack_file_path)
        self.logger.info(
            f"Server '{self.server_name}': Processing .mcpack '{mcpack_filename}'."
        )

        temp_dir = tempfile.mkdtemp(prefix=f"mcpack_{self.server_name}_")
        self.logger.debug(
            f"Created temporary directory for .mcpack extraction: {temp_dir}"
        )

        try:
            try:
                self.logger.info(f"Extracting '{mcpack_filename}' to temp dir...")
                with zipfile.ZipFile(mcpack_file_path, "r") as zip_ref:
                    zip_ref.extractall(temp_dir)
                self.logger.debug(f"Successfully extracted '{mcpack_filename}'.")
            except zipfile.BadZipFile as e:
                raise ExtractError(
                    f"Invalid .mcpack (not a zip file): {mcpack_filename}"
                ) from e
            except OSError as e:
                raise FileOperationError(
                    f"Error extracting '{mcpack_filename}': {e}"
                ) from e

            # Delegate to the installation method.
            self._install_pack_from_extracted_data(temp_dir, mcpack_file_path)

        finally:
            if os.path.isdir(temp_dir):
                try:
                    self.logger.debug(f"Cleaning up temp directory: {temp_dir}")
                    shutil.rmtree(temp_dir)
                except OSError as e:
                    self.logger.warning(
                        f"Could not remove temp directory '{temp_dir}': {e}",
                        exc_info=True,
                    )

    def _install_pack_from_extracted_data(
        self, extracted_pack_dir: str, original_mcpack_path: str
    ) -> None:
        """Installs a behavior or resource pack from its extracted files into the active world.

        This core installation logic performs these actions:

            1. Reads and validates the ``manifest.json`` from the ``extracted_pack_dir``
               using :meth:`._extract_manifest_info` to get pack metadata (type, UUID,
               version, name).
            2. Determines the target installation path within the active world's
               ``behavior_packs`` or ``resource_packs`` directory. The folder name
               includes the pack name and version for uniqueness (e.g., ``MyPack_1.0.0``).
               Requires :meth:`~.core.server.state_mixin.ServerStateMixin.get_world_name`.
            3. Copies the contents from ``extracted_pack_dir`` to this target path.
               If a directory for this pack version already exists, it's removed first
               to ensure a clean installation.
            4. Updates the corresponding world activation JSON file
               (``world_behavior_packs.json`` or ``world_resource_packs.json``)
               using :meth:`._update_world_pack_json_file` to activate the pack.

        Args:
            extracted_pack_dir (str): The absolute path to the temporary
                directory containing the extracted contents of a pack.
            original_mcpack_path (str): The original path of the ``.mcpack``
                file, used for logging and potentially for deriving a pack name if
                the manifest is severely corrupted (though current logic prioritizes manifest).

        Raises:
            AppFileNotFoundError: If ``manifest.json`` is missing in ``extracted_pack_dir``
                (raised by :meth:`._extract_manifest_info`).
            ConfigParseError: If the ``manifest.json`` is malformed or missing
                required information (raised by :meth:`._extract_manifest_info`).
            UserInputError: If the pack type specified in the manifest is unknown
                (not 'data' or 'resources').
            FileOperationError: If any file I/O operation fails during the
                installation, such as creating directories, copying files, or
                updating the world JSON files.
            AttributeError: If :meth:`~.core.server.state_mixin.ServerStateMixin.get_world_name`
                is not available.
        """
        original_mcpack_filename = os.path.basename(original_mcpack_path)
        self.logger.debug(
            f"Server '{self.server_name}': Processing manifest for pack from '{original_mcpack_filename}' in '{extracted_pack_dir}'."
        )

        try:
            # Get metadata from the manifest.
            pack_type, uuid, version_list, addon_name = self._extract_manifest_info(
                extracted_pack_dir
            )
            self.logger.info(
                f"Manifest for '{original_mcpack_filename}': Type='{pack_type}', UUID='{uuid}', Version='{version_list}', Name='{addon_name}'"
            )

            # --- Installation Logic ---
            active_world_name = self.get_world_name()

            # Define paths within the active world.
            active_world_dir = os.path.join(
                self.server_dir, "worlds", active_world_name
            )
            behavior_packs_target_base = os.path.join(
                active_world_dir, "behavior_packs"
            )
            resource_packs_target_base = os.path.join(
                active_world_dir, "resource_packs"
            )
            world_behavior_packs_json = os.path.join(
                active_world_dir, "world_behavior_packs.json"
            )
            world_resource_packs_json = os.path.join(
                active_world_dir, "world_resource_packs.json"
            )

            os.makedirs(behavior_packs_target_base, exist_ok=True)
            os.makedirs(resource_packs_target_base, exist_ok=True)

            # Create a unique, file-safe folder name for this specific version of the addon.
            version_str = ".".join(map(str, version_list))
            safe_addon_folder_name = (
                re.sub(r'[<>:"/\\|?*]', "_", addon_name) + f"_{version_str}"
            )

            # Determine target paths based on pack type.
            target_install_path: str
            target_world_json_file: str
            pack_type_friendly_name: str

            if pack_type == "data":  # Behavior pack
                target_install_path = os.path.join(
                    behavior_packs_target_base, safe_addon_folder_name
                )
                target_world_json_file = world_behavior_packs_json
                pack_type_friendly_name = "behavior"
            elif pack_type == "resources":  # Resource pack
                target_install_path = os.path.join(
                    resource_packs_target_base, safe_addon_folder_name
                )
                target_world_json_file = world_resource_packs_json
                pack_type_friendly_name = "resource"
            else:
                raise UserInputError(
                    f"Cannot install unknown pack type: '{pack_type}' for '{original_mcpack_filename}'"
                )

            self.logger.info(
                f"Installing {pack_type_friendly_name} pack '{addon_name}' v{version_str} into: {target_install_path}"
            )

            # Perform a clean install by removing the old version if it exists.
            if os.path.isdir(target_install_path):
                self.logger.debug(
                    f"Removing existing target directory: {target_install_path}"
                )
                shutil.rmtree(target_install_path)

            shutil.copytree(extracted_pack_dir, target_install_path)
            self.logger.debug(f"Copied pack contents to '{target_install_path}'.")

            # Activate the pack by adding it to the world's JSON file.
            self._update_world_pack_json_file(
                target_world_json_file, uuid, version_list
            )
            self.logger.info(
                f"Successfully installed and activated {pack_type_friendly_name} pack '{addon_name}' v{version_str} for server '{self.server_name}'."
            )

        except (AppFileNotFoundError, ConfigParseError) as e_manifest:
            self.logger.error(
                f"Failed to process manifest for '{original_mcpack_filename}': {e_manifest}",
                exc_info=True,
            )
            raise
        except (FileOperationError, UserInputError, AppFileNotFoundError) as e_install:
            self.logger.error(
                f"Failed to install pack from '{original_mcpack_filename}': {e_install}",
                exc_info=True,
            )
            raise
        except Exception as e_unexp:
            self.logger.error(
                f"Unexpected error installing pack '{original_mcpack_filename}': {e_unexp}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Unexpected error processing pack '{original_mcpack_filename}' for server '{self.server_name}': {e_unexp}"
            ) from e_unexp

    def _extract_manifest_info(
        self, extracted_pack_dir: str
    ) -> Tuple[str, str, List[int], str]:
        """Extracts and validates key information from a pack's ``manifest.json`` file.

        This method reads the ``manifest.json`` located in the ``extracted_pack_dir``,
        parses its JSON content, and extracts essential metadata about the pack.
        It specifically looks for the pack's display name, UUID, version (as a
        three-part integer list), and type ('data' for behavior packs,
        'resources' for resource packs).

        Args:
            extracted_pack_dir (str): The absolute path to the directory
                containing the ``manifest.json`` file for the pack.

        Returns:
            Tuple[str, str, List[int], str]: A tuple containing:
                - ``pack_type`` (str): The type of the pack, normalized to lowercase
                  (e.g., 'data', 'resources').
                - ``uuid`` (str): The pack's unique identifier (UUID).
                - ``version`` (List[int]): The pack's version, as a list of three
                  integers (e.g., ``[1, 0, 0]``).
                - ``name`` (str): The human-readable display name of the pack.

        Raises:
            AppFileNotFoundError: If ``manifest.json`` is not found within
                ``extracted_pack_dir`` or is not a file.
            ConfigParseError: If the ``manifest.json`` content is not valid JSON,
                is not a JSON object, or is missing essential fields (e.g.,
                ``header.uuid``, ``header.version``, ``header.name``,
                ``modules`` array, or a valid ``modules[0].type``).
            FileOperationError: If an OS-level error occurs while trying to read
                the ``manifest.json`` file (e.g., permission issues).
            UserInputError: If the pack type specified in the manifest's module
                section is not 'data' or 'resources' (case-insensitive).
        """
        manifest_file = os.path.join(extracted_pack_dir, "manifest.json")
        self.logger.debug(f"Attempting to read manifest file: {manifest_file}")

        if not os.path.isfile(manifest_file):
            raise AppFileNotFoundError(manifest_file, "Manifest file")

        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)

            if not isinstance(manifest_data, dict):
                raise ConfigParseError("Manifest content is not a valid JSON object.")

            header = manifest_data.get("header")
            if not isinstance(header, dict):
                raise ConfigParseError("Manifest missing or invalid 'header' object.")

            # Extract required fields from the header.
            uuid_val = header.get("uuid")
            version_val = header.get("version")
            name_val = header.get("name")

            # Extract the pack type from the modules section.
            modules = manifest_data.get("modules")
            if not isinstance(modules, list) or not modules:
                raise ConfigParseError("Manifest missing or invalid 'modules' array.")
            first_module = modules[0]
            if not isinstance(first_module, dict):
                raise ConfigParseError(
                    "First item in 'modules' array is not a valid object."
                )
            pack_type_val = first_module.get("type")

            # Validate the extracted fields to ensure they exist and have the correct type.
            if not (
                uuid_val
                and isinstance(uuid_val, str)
                and version_val
                and isinstance(version_val, list)
                and len(version_val) == 3
                and all(isinstance(v, int) for v in version_val)
                and name_val
                and isinstance(name_val, str)
                and pack_type_val
                and isinstance(pack_type_val, str)
            ):
                missing_details = f"uuid: {uuid_val}, version: {version_val}, name: {name_val}, type: {pack_type_val}"
                raise ConfigParseError(
                    f"Invalid manifest structure in {manifest_file}. Details: {missing_details}"
                )

            pack_type_cleaned = pack_type_val.lower()
            # Minecraft uses 'data' for behavior packs and 'resources' for resource packs.
            if pack_type_cleaned not in ("data", "resources"):
                raise UserInputError(
                    f"Pack type '{pack_type_cleaned}' from manifest is not 'data' or 'resources'."
                )

            self.logger.debug(
                f"Extracted manifest: Type='{pack_type_cleaned}', UUID='{uuid_val}', Version='{version_val}', Name='{name_val}'"
            )
            return pack_type_cleaned, uuid_val, version_val, name_val

        except ValueError as e:
            raise ConfigParseError(
                f"Invalid JSON in manifest '{manifest_file}': {e}"
            ) from e
        except OSError as e:
            raise FileOperationError(
                f"Cannot read manifest file '{manifest_file}': {e}"
            ) from e

    def _update_world_pack_json_file(
        self, world_json_file_path: str, pack_uuid: str, pack_version_list: List[int]
    ) -> None:
        """Adds or updates a pack entry in a world's activation JSON file.

        This method manages the activation of a behavior or resource pack by
        modifying the world's corresponding JSON configuration file (e.g.,
        ``world_behavior_packs.json`` or ``world_resource_packs.json``).

        The logic is as follows:

            1. Reads the existing list of activated packs from ``world_json_file_path``.
               If the file doesn't exist or is invalid, it starts with an empty list.
            2. Searches for an existing entry with the given ``pack_uuid``.
               - If found, it compares the ``pack_version_list`` with the existing
                 version. If the new version is greater than or equal to the existing
                 one, the entry is updated with the new version.
               - If an existing entry has an invalid version format, it's overwritten.
            3. If no entry with ``pack_uuid`` is found, a new entry for the pack
               (with its UUID and version) is appended to the list.
            4. Writes the updated list of packs back to the ``world_json_file_path``,
               pretty-printed with an indent of 2.

        The directory for ``world_json_file_path`` is created if it doesn't exist.

        Args:
            world_json_file_path (str): The absolute path to the world's pack
                activation JSON file (e.g., ``.../worlds/MyWorld/world_behavior_packs.json``).
            pack_uuid (str): The UUID of the pack to add or update in the activation list.
            pack_version_list (List[int]): The version of the pack as a list of
                three integers (e.g., ``[1, 0, 0]``).

        Raises:
            FileOperationError: If the JSON file cannot be read or written due to
                OS-level errors (e.g., permission issues, disk full), or if
                creating the parent directory fails.
        """
        json_filename_basename = os.path.basename(world_json_file_path)
        self.logger.debug(
            f"Updating world pack JSON '{json_filename_basename}' for UUID: {pack_uuid}, Version: {pack_version_list}"
        )

        packs_list = []
        try:
            # Safely load the existing list of packs.
            if os.path.exists(world_json_file_path):
                with open(world_json_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content.strip():
                        loaded_packs = json.loads(content)
                        if isinstance(loaded_packs, list):
                            packs_list = loaded_packs
                        else:
                            self.logger.warning(
                                f"'{json_filename_basename}' content not a list. Will overwrite."
                            )
        except ValueError as e:
            self.logger.warning(
                f"Invalid JSON in '{json_filename_basename}'. Will overwrite. Error: {e}"
            )
        except OSError as e:
            raise FileOperationError(
                f"Failed to read world pack JSON '{json_filename_basename}': {e}"
            ) from e

        pack_entry_found = False
        input_version_tuple = tuple(pack_version_list)

        # Iterate through existing packs to find a match by UUID.
        for i, existing_pack_entry in enumerate(packs_list):
            if (
                isinstance(existing_pack_entry, dict)
                and existing_pack_entry.get("pack_id") == pack_uuid
            ):
                pack_entry_found = True
                existing_version_list = existing_pack_entry.get("version")
                # If the existing entry has a valid version, compare it.
                if (
                    isinstance(existing_version_list, list)
                    and len(existing_version_list) == 3
                ):
                    existing_version_tuple = tuple(existing_version_list)
                    # Update if the new version is newer or the same.
                    if input_version_tuple >= existing_version_tuple:
                        if input_version_tuple > existing_version_tuple:
                            self.logger.info(
                                f"Updating pack '{pack_uuid}' in '{json_filename_basename}' from v{existing_version_list} to v{pack_version_list}."
                            )
                        packs_list[i] = {
                            "pack_id": pack_uuid,
                            "version": pack_version_list,
                        }
                else:
                    # Overwrite if the existing version format is invalid.
                    self.logger.warning(
                        f"Pack '{pack_uuid}' in '{json_filename_basename}' has invalid version. Overwriting with v{pack_version_list}."
                    )
                    packs_list[i] = {"pack_id": pack_uuid, "version": pack_version_list}
                break

        # If no matching pack was found, add it as a new entry.
        if not pack_entry_found:
            self.logger.info(
                f"Adding new pack '{pack_uuid}' v{pack_version_list} to '{json_filename_basename}'."
            )
            packs_list.append({"pack_id": pack_uuid, "version": pack_version_list})

        try:
            os.makedirs(os.path.dirname(world_json_file_path), exist_ok=True)
            with open(world_json_file_path, "w", encoding="utf-8") as f:
                json.dump(packs_list, f, indent=2, sort_keys=True)
            self.logger.debug(
                f"Successfully wrote updated packs to '{json_filename_basename}'."
            )
        except OSError as e:
            raise FileOperationError(
                f"Failed to write world pack JSON '{json_filename_basename}': {e}"
            ) from e

    def list_world_addons(
        self, world_name: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Lists all behavior and resource packs for a specified world.

        This method provides a detailed inventory of addons by:

            1. Scanning the physical pack folders (``behavior_packs`` and ``resource_packs``)
               within the specified world's directory to find all installed packs by
               reading their ``manifest.json`` files.
            2. Reading the world's activation JSON files (``world_behavior_packs.json``
               and ``world_resource_packs.json``) to determine which packs are active.
            3. Comparing these two sets of information to determine the status of each pack.

        The status can be:
            - ``ACTIVE``: The pack is physically present and listed in the activation file.
            - ``INACTIVE``: The pack is physically present but not listed in the activation file.
            - ``ORPHANED``: The pack is listed in the activation file but not physically present.

        Args:
            world_name (Optional[str]): The name of the world to inspect.
                If ``None`` (default), uses the server's currently active world name
                obtained via :meth:`~.core.server.state_mixin.ServerStateMixin.get_world_name`.

        Returns:
            Dict[str, List[Dict[str, Any]]]: A dictionary with two keys:
            ``"behavior_packs"`` and ``"resource_packs"``. Each key maps to a list
            of dictionaries, where each dictionary represents an addon with the
            following string keys:

                - ``"name"`` (str): The display name of the pack from its manifest.
                - ``"uuid"`` (str): The UUID of the pack from its manifest.
                - ``"version"`` (List[int]): The version of the pack (e.g., ``[1, 0, 0]``).
                - ``"status"`` (str): The activation status: 'ACTIVE', 'INACTIVE', or 'ORPHANED'.

            The lists of pack dictionaries are sorted by pack name.

        Raises:
            AppFileNotFoundError: If the directory for the specified ``world_name``
                does not exist.
            AttributeError: If :meth:`~.core.server.state_mixin.ServerStateMixin.get_world_name`
                is not available when ``world_name`` is ``None``.
        """
        if world_name is None:
            world_name = self.get_world_name()  # type: ignore

        self.logger.info(
            f"Listing addons for world '{world_name}' in server '{self.server_name}'."
        )

        world_dir = os.path.join(self.server_dir, "worlds", world_name)
        if not os.path.isdir(world_dir):
            raise AppFileNotFoundError(world_dir, f"World directory for '{world_name}'")

        # Get lists of physical and activated packs for both types.
        physical_bps = self._scan_physical_packs(world_dir, "behavior_packs")
        activated_bps_list = self._read_world_activation_json(
            os.path.join(world_dir, "world_behavior_packs.json")
        )

        physical_rps = self._scan_physical_packs(world_dir, "resource_packs")
        activated_rps_list = self._read_world_activation_json(
            os.path.join(world_dir, "world_resource_packs.json")
        )

        # Reconcile the lists to determine status for each pack.
        behavior_pack_results = self._compare_physical_and_activated(
            physical_bps, activated_bps_list
        )
        resource_pack_results = self._compare_physical_and_activated(
            physical_rps, activated_rps_list
        )

        return {
            "behavior_packs": behavior_pack_results,
            "resource_packs": resource_pack_results,
        }

    def _scan_physical_packs(
        self, world_dir: str, pack_folder_name: str
    ) -> List[Dict[str, Any]]:
        """Scans a world's pack subfolder (e.g., 'behavior_packs') and parses manifests.

        This method iterates through each subdirectory within the specified
        ``pack_folder_name`` (e.g., ``behavior_packs`` or ``resource_packs``)
        located inside the given ``world_dir``. For each subdirectory found,
        it attempts to read and parse its ``manifest.json`` file using
        :meth:`._extract_manifest_info`.

        If a manifest is successfully parsed, a dictionary containing the pack's
        name, UUID, version, and its full path is added to the returned list.
        If a manifest cannot be read or is invalid, a warning is logged, and
        that pack directory is skipped.

        Args:
            world_dir (str): The absolute path to the world directory.
            pack_folder_name (str): The name of the pack subfolder to scan
                (typically ``"behavior_packs"`` or ``"resource_packs"``).

        Returns:
            List[Dict[str, Any]]: A list of dictionaries. Each dictionary
            represents a physically installed pack and contains the following keys:

                - ``"name"`` (str): The pack's display name.
                - ``"uuid"`` (str): The pack's UUID.
                - ``"version"`` (List[int]): The pack's version (e.g., ``[1, 0, 0]``).
                - ``"path"`` (str): The absolute path to the pack's directory.

            Returns an empty list if the ``pack_folder_name`` does not exist or
            contains no valid packs.
        """
        pack_base_dir = os.path.join(world_dir, pack_folder_name)
        if not os.path.isdir(pack_base_dir):
            return []

        installed_packs = []
        for pack_dir_name in os.listdir(pack_base_dir):
            pack_full_path = os.path.join(pack_base_dir, pack_dir_name)
            if os.path.isdir(pack_full_path):
                try:
                    _pack_type, uuid, version, name = self._extract_manifest_info(
                        pack_full_path
                    )
                    installed_packs.append(
                        {
                            "name": name,
                            "uuid": uuid,
                            "version": version,
                            "path": pack_full_path,
                        }
                    )
                except (AppFileNotFoundError, ConfigParseError) as e:
                    self.logger.warning(
                        f"Could not read manifest for pack in '{pack_full_path}'. Skipping. Reason: {e}"
                    )
        return installed_packs

    def _read_world_activation_json(
        self, world_json_file_path: str
    ) -> List[Dict[str, Any]]:
        """Safely reads and parses a world's pack activation JSON file.

        This method attempts to read the specified JSON file (e.g.,
        ``world_behavior_packs.json`` or ``world_resource_packs.json``).
        It expects the file to contain a JSON list of pack activation entries.

        If the file does not exist, is empty, contains invalid JSON, or if its
        top-level structure is not a list, an empty list is returned, and a
        warning may be logged.

        Args:
            world_json_file_path (str): The absolute path to the world's pack
                activation JSON file.

        Returns:
            List[Dict[str, Any]]: A list of pack activation entries (dictionaries,
            typically with ``"pack_id"`` and ``"version"`` keys) if the file is
            valid and contains a list. Returns an empty list otherwise.
        """
        if not os.path.exists(world_json_file_path):
            return []

        try:
            with open(world_json_file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip():
                    return []
                data = json.loads(content)
                if isinstance(data, list):
                    return data
                else:
                    self.logger.warning(
                        f"File '{world_json_file_path}' does not contain a JSON list. Treating as empty."
                    )
                    return []
        except (ValueError, OSError) as e:
            self.logger.error(f"Failed to read or parse '{world_json_file_path}': {e}")
            return []

    def _compare_physical_and_activated(
        self, physical: List[Dict[str, Any]], activated: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Compares lists of physical and activated packs to determine addon statuses.

        This utility method reconciles two lists:

            1. ``physical``: Packs found by scanning the filesystem (e.g., from
               :meth:`._scan_physical_packs`). Each dict should contain 'name', 'uuid', 'version'.
            2. ``activated``: Packs listed in a world's activation JSON file (e.g., from
               :meth:`._read_world_activation_json`). Each dict should contain 'pack_id' (UUID)
               and 'version'.

        It determines the status for each pack based on this comparison:

            - ``ACTIVE``: The pack is present in both ``physical`` and ``activated`` lists
              (matched by UUID).
            - ``INACTIVE``: The pack is present in the ``physical`` list but not in the
              ``activated`` list.
            - ``ORPHANED``: The pack is present in the ``activated`` list but not in the
              ``physical`` list.

        Args:
            physical (List[Dict[str, Any]]): A list of dictionaries representing
                physically installed packs. Expected keys: "name", "uuid", "version".
            activated (List[Dict[str, Any]]): A list of dictionaries representing
                packs listed in an activation JSON file. Expected keys: "pack_id", "version".

        Returns:
            List[Dict[str, Any]]: A new list of pack dictionaries, sorted by pack
            name. Each dictionary includes the original pack information (name, uuid,
            version) plus an added ``"status"`` key (str) indicating 'ACTIVE',
            'INACTIVE', or 'ORPHANED'. For orphaned packs, the name might be
            "Unknown (Orphaned)" if not found in the physical list.
        """
        results = []
        activated_uuids = {
            entry["pack_id"] for entry in activated if "pack_id" in entry
        }

        # Process physically present packs to determine if they are active or inactive.
        for p_pack in physical:
            pack_info = {
                "name": p_pack["name"],
                "uuid": p_pack["uuid"],
                "version": p_pack["version"],
                "status": "ACTIVE" if p_pack["uuid"] in activated_uuids else "INACTIVE",
            }
            results.append(pack_info)

        # Find orphaned activations (activated but not physically present).
        physical_uuids = {p["uuid"] for p in physical}
        orphaned_uuids = activated_uuids - physical_uuids

        for orphan_uuid in orphaned_uuids:
            # Find the corresponding entry in the activated list to get version info.
            orphan_entry = next(
                (a for a in activated if a.get("pack_id") == orphan_uuid), None
            )
            orphan_version = (
                orphan_entry.get("version", [0, 0, 0]) if orphan_entry else [0, 0, 0]
            )
            results.append(
                {
                    "name": "Unknown (Orphaned)",
                    "uuid": orphan_uuid,
                    "version": orphan_version,
                    "status": "ORPHANED",
                }
            )

        return sorted(results, key=lambda x: x["name"])

    def export_addon(
        self,
        pack_uuid: str,
        pack_type: str,
        export_dir: str,
        world_name: Optional[str] = None,
    ) -> str:
        """Exports a specific installed addon from a world into a ``.mcpack`` file.

        This method locates an installed behavior or resource pack within the
        specified world by its UUID, then archives its contents into a new
        ``.mcpack`` file. The exported file is named using the pack's name
        and version (e.g., ``MyPack_1.0.0.mcpack``) and saved in the
        ``export_dir``.

        Args:
            pack_uuid (str): The UUID of the pack to export.
            pack_type (str): The type of pack; must be either ``"behavior"`` or
                ``"resource"``.
            export_dir (str): The absolute path to the directory where the
                ``.mcpack`` file will be saved. This directory will be created
                if it does not already exist.
            world_name (Optional[str]): The name of the world from which to export
                the addon. If ``None`` (default), uses the server's currently active
                world name.

        Returns:
            str: The absolute path to the created ``.mcpack`` file.

        Raises:
            MissingArgumentError: If ``pack_uuid``, ``pack_type``, or ``export_dir``
                are empty or not provided.
            UserInputError: If ``pack_type`` is not ``"behavior"`` or ``"resource"``.
            AppFileNotFoundError: If the specified pack (by UUID and type) cannot be
                found in the physical ``behavior_packs`` or ``resource_packs``
                folder of the world, or if the world directory itself is missing.
            FileOperationError: If any OS-level error occurs during directory
                creation, file scanning, or ``.mcpack`` archive creation (e.g.,
                permission issues, disk full).
            AttributeError: If methods like
                :meth:`~.core.server.state_mixin.ServerStateMixin.get_world_name`
                are unavailable when ``world_name`` is ``None``.
        """
        if not pack_uuid or not pack_type or not export_dir:
            raise MissingArgumentError(
                "Pack UUID, pack type, and export directory are required."
            )
        if pack_type not in ("behavior", "resource"):
            raise UserInputError("Pack type must be 'behavior' or 'resource'.")

        if world_name is None:
            world_name = self.get_world_name()

        self.logger.info(
            f"Exporting {pack_type} pack '{pack_uuid}' from world '{world_name}'."
        )

        # Find the source directory of the pack to be exported.
        world_dir = os.path.join(self.server_dir, "worlds", world_name)
        pack_folder_name = f"{pack_type}_packs"
        physical_packs = self._scan_physical_packs(world_dir, pack_folder_name)
        target_pack = next((p for p in physical_packs if p["uuid"] == pack_uuid), None)

        if not target_pack:
            raise AppFileNotFoundError(
                f"pack with UUID {pack_uuid}",
                f"{pack_folder_name} in world '{world_name}'",
            )

        pack_name = target_pack["name"]
        pack_version = ".".join(map(str, target_pack["version"]))
        pack_source_path = target_pack["path"]

        # Create a file-safe name for the exported archive.
        safe_pack_name = re.sub(r'[<>:"/\\|?* ]', "_", pack_name)
        export_filename = f"{safe_pack_name}_{pack_version}.mcpack"
        export_file_path = os.path.join(export_dir, export_filename)

        os.makedirs(export_dir, exist_ok=True)

        try:
            # Create the zip archive, ensuring paths inside are relative.
            self.logger.debug(f"Zipping '{pack_source_path}' to '{export_file_path}'")
            with zipfile.ZipFile(export_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _dirs, files in os.walk(pack_source_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Archive name is relative to the pack's source directory.
                        archive_name = os.path.relpath(file_path, pack_source_path)
                        zipf.write(file_path, archive_name)
            self.logger.info(
                f"Successfully exported addon '{pack_name}' to '{export_file_path}'."
            )
            return export_file_path
        except (OSError, zipfile.BadZipFile) as e:
            raise FileOperationError(
                f"Could not create addon archive for '{pack_name}': {e}"
            ) from e

    def remove_addon(
        self, pack_uuid: str, pack_type: str, world_name: Optional[str] = None
    ) -> None:
        """Removes a specific addon from a world.

        .. warning::
            This is a destructive operation. It permanently deletes the addon's
            files from the world's ``behavior_packs`` or ``resource_packs``
            directory and deactivates the addon by removing its entry from the
            world's corresponding activation JSON file (e.g.,
            ``world_behavior_packs.json``).

        If the addon's files are not found, it will still attempt to remove its
        entry from the activation JSON file.

        Args:
            pack_uuid (str): The UUID of the pack to remove.
            pack_type (str): The type of pack; must be either ``"behavior"`` or
                ``"resource"``.
            world_name (Optional[str]): The name of the world from which to remove
                the addon. If ``None`` (default), uses the server's currently active
                world name.

        Raises:
            MissingArgumentError: If ``pack_uuid`` or ``pack_type`` are empty or
                not provided.
            UserInputError: If ``pack_type`` is not ``"behavior"`` or ``"resource"``.
            FileOperationError: If an OS-level error occurs during file/directory
                deletion or when updating the world's activation JSON file.
            AttributeError: If methods like
                :meth:`~.core.server.state_mixin.ServerStateMixin.get_world_name`
                are unavailable when ``world_name`` is ``None``.
        """
        if not pack_uuid or not pack_type:
            raise MissingArgumentError("Pack UUID and pack type are required.")
        if pack_type not in ("behavior", "resource"):
            raise UserInputError("Pack type must be 'behavior' or 'resource'.")

        if world_name is None:
            world_name = self.get_world_name()

        self.logger.info(
            f"Removing {pack_type} pack '{pack_uuid}' from world '{world_name}'."
        )

        world_dir = os.path.join(self.server_dir, "worlds", world_name)
        pack_folder_name = f"{pack_type}_packs"
        physical_packs = self._scan_physical_packs(world_dir, pack_folder_name)

        # Find the pack to get its path for deletion.
        target_pack = next((p for p in physical_packs if p["uuid"] == pack_uuid), None)
        if not target_pack:
            # If pack files are already gone, still try to clean the JSON file.
            self.logger.warning(
                f"Pack files for UUID '{pack_uuid}' not found. Attempting to clean activation JSON."
            )
        else:
            pack_name = target_pack["name"]
            pack_source_path = target_pack["path"]
            try:
                self.logger.debug(f"Deleting pack folder: {pack_source_path}")
                shutil.rmtree(pack_source_path)
                self.logger.info(f"Successfully deleted files for pack '{pack_name}'.")
            except OSError as e:
                raise FileOperationError(
                    f"Failed to delete addon folder for '{pack_name}': {e}"
                ) from e

        # Always attempt to remove the pack from the activation JSON.
        world_json_path = os.path.join(world_dir, f"world_{pack_folder_name}.json")
        self._remove_pack_from_world_json(world_json_path, pack_uuid)

    def _remove_pack_from_world_json(
        self, world_json_file_path: str, pack_uuid: str
    ) -> None:
        """Removes a specific pack entry from a world's pack activation JSON file.

        This method reads the specified world activation JSON file (e.g.,
        ``world_behavior_packs.json``), filters out any entry that matches the
        given ``pack_uuid``, and then writes the modified list back to the file.

        If the activation file does not exist, or if the pack UUID is not found
        in the file, the method does nothing further after logging this.

        Args:
            world_json_file_path (str): The absolute path to the world's pack
                activation JSON file (e.g., ``.../worlds/MyWorld/world_behavior_packs.json``).
            pack_uuid (str): The UUID of the pack to remove from the activation list.

        Raises:
            FileOperationError: If the JSON file exists but cannot be written back
                due to OS-level errors (e.g., permission issues, disk full).
                Reading errors are handled internally by :meth:`._read_world_activation_json`.
        """
        json_filename = os.path.basename(world_json_file_path)
        if not os.path.exists(world_json_file_path):
            self.logger.debug(
                f"Activation file '{json_filename}' not found. Nothing to remove."
            )
            return

        original_packs_list = self._read_world_activation_json(world_json_file_path)
        if not original_packs_list:
            return  # File was empty or invalid, so nothing to do.

        # Create a new list excluding the pack to be removed.
        updated_packs_list = [
            p for p in original_packs_list if p.get("pack_id") != pack_uuid
        ]

        if len(original_packs_list) == len(updated_packs_list):
            self.logger.debug(
                f"Pack UUID '{pack_uuid}' not found in '{json_filename}'. No changes made."
            )
            return

        try:
            with open(world_json_file_path, "w", encoding="utf-8") as f:
                json.dump(updated_packs_list, f, indent=2, sort_keys=True)
            self.logger.info(
                f"Removed pack '{pack_uuid}' from activation file '{json_filename}'."
            )
        except OSError as e:
            raise FileOperationError(
                f"Failed to write updated activation file '{json_filename}': {e}"
            ) from e
