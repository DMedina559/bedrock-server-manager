"""Bedrock addon component."""

import glob
import json
import os
import re
import shutil
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import aiofiles
import aiofiles.os
import aiofiles.ospath

from ...error import (
    AppFileNotFoundError,
    ConfigParseError,
    ExtractError,
    FileOperationError,
    MissingArgumentError,
    UserInputError,
)
from ...utils.io import load_json, save_json
from ...utils.threads import run_in_thread
from ..files import extract_archive, file_transaction, temporary_directory
from ..manifests import PackManifest

if TYPE_CHECKING:
    from ..bedrock_server import BedrockServer


class ServerAddons:
    """Addon operations for one Bedrock server."""

    def __init__(self, server: "BedrockServer") -> None:
        self.server = server

    async def process_addon_file(self, addon_file_path: str) -> None:
        """Processes an addon file asynchronously.

        This method acts as a high-level dispatcher for asynchronous addon processing.
        It inspects the file extension of the provided ``addon_file_path`` to determine if it's an ``.mcaddon``
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
        async with self.server.operation_lock:
            if not addon_file_path:
                raise MissingArgumentError("Addon file path cannot be empty.")
            self.server.logger.info(
                f"Server '{self.server.server_name}': Processing addon file '{os.path.basename(addon_file_path)}'."
            )
            if not await aiofiles.ospath.isfile(addon_file_path):
                raise AppFileNotFoundError(addon_file_path, "Addon file")
            addon_file_lower = addon_file_path.lower()
            if addon_file_lower.endswith(".mcaddon"):
                self.server.logger.debug("Detected .mcaddon file type. Delegating.")
                await self._process_mcaddon_archive(addon_file_path)
            elif addon_file_lower.endswith(".mcpack"):
                self.server.logger.debug("Detected .mcpack file type. Delegating.")
                await self._process_mcpack_archive(addon_file_path)
            else:
                err_msg = f"Unsupported addon file type: '{os.path.basename(addon_file_path)}'. Only .mcaddon and .mcpack are supported."
                self.server.logger.error(err_msg)
                raise UserInputError(err_msg)

    async def list_installed_addons(
        self, world_name: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Lists all behavior and resource packs for a specified world asynchronously.

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
                obtained via :meth:`~.core.bedrock_server.BedrockServer.get_world_name`.

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
            AttributeError: If :meth:`~.core.bedrock_server.BedrockServer.get_world_name`
                is not available when ``world_name`` is ``None``.
        """
        if world_name is None:
            world_name = await self.server.get_world_name()
        self.server.logger.info(
            f"Listing addons for world '{world_name}' in server '{self.server.server_name}'."
        )
        world_dir = os.path.join(self.server.paths.server_dir, "worlds", world_name)
        if not await aiofiles.ospath.isdir(world_dir):
            raise AppFileNotFoundError(world_dir, f"World directory for '{world_name}'")
        physical_bps = await self._scan_physical_packs(world_dir, "behavior_packs")
        activated_bps_list = await self._read_world_activation_json(
            os.path.join(world_dir, "world_behavior_packs.json")
        )
        physical_rps = await self._scan_physical_packs(world_dir, "resource_packs")
        activated_rps_list = await self._read_world_activation_json(
            os.path.join(world_dir, "world_resource_packs.json")
        )
        behavior_pack_results = await self._compare_physical_and_activated(
            physical_bps, activated_bps_list
        )
        resource_pack_results = await self._compare_physical_and_activated(
            physical_rps, activated_rps_list
        )
        for pack in behavior_pack_results:
            if "path" in pack:
                icon_path = os.path.join(pack["path"], "pack_icon.png")
                if await aiofiles.ospath.exists(icon_path):
                    pack["icon"] = icon_path
        for pack in resource_pack_results:
            if "path" in pack:
                icon_path = os.path.join(pack["path"], "pack_icon.png")
                if await aiofiles.ospath.exists(icon_path):
                    pack["icon"] = icon_path
        return {
            "behavior_packs": behavior_pack_results,
            "resource_packs": resource_pack_results,
        }

    async def enable_addon(
        self, pack_uuid: str, pack_type: str, world_name: Optional[str] = None
    ) -> None:
        """Enables a physically installed addon in a world asynchronously.

        Args:
            pack_uuid (str): The UUID of the pack to enable.
            pack_type (str): The type of pack; must be either ``"behavior"`` or ``"resource"``.
            world_name (Optional[str]): The name of the world.
        """
        async with self.server.operation_lock:
            if not pack_uuid or not pack_type:
                raise MissingArgumentError("Pack UUID and pack type are required.")
            if pack_type not in ("behavior", "resource"):
                raise UserInputError("Pack type must be 'behavior' or 'resource'.")
            if world_name is None:
                world_name = await self.server.get_world_name()
            self.server.logger.info(
                f"Enabling {pack_type} pack '{pack_uuid}' in world '{world_name}'."
            )
            world_dir = os.path.join(self.server.paths.server_dir, "worlds", world_name)
            pack_folder_name = f"{pack_type}_packs"
            physical_packs = await self._scan_physical_packs(
                world_dir, pack_folder_name
            )
            target_pack = next(
                (p for p in physical_packs if p["uuid"] == pack_uuid), None
            )
            if not target_pack:
                raise AppFileNotFoundError(
                    f"pack with UUID {pack_uuid}",
                    f"{pack_folder_name} in world '{world_name}'",
                )
            world_json_path = os.path.join(world_dir, f"world_{pack_folder_name}.json")
            await self._update_world_pack_json_file(
                world_json_path, pack_uuid, target_pack["version"]
            )

    async def update_subpack(
        self,
        pack_uuid: str,
        pack_type: str,
        subpack_name: str,
        world_name: Optional[str] = None,
    ) -> None:
        """Updates the active subpack for an already enabled addon asynchronously.

        Args:
            pack_uuid (str): The UUID of the active pack.
            pack_type (str): The type of pack; must be either ``"behavior"`` or ``"resource"``.
            subpack_name (str): The new subpack folder name to set.
            world_name (Optional[str]): The name of the world.
        """
        async with self.server.operation_lock:
            if not pack_uuid or not pack_type or (not subpack_name):
                raise MissingArgumentError(
                    "Pack UUID, pack type, and subpack name are required."
                )
            if pack_type not in ("behavior", "resource"):
                raise UserInputError("Pack type must be 'behavior' or 'resource'.")
            if world_name is None:
                world_name = await self.server.get_world_name()
            self.server.logger.info(
                f"Updating subpack to '{subpack_name}' for {pack_type} pack '{pack_uuid}' in world '{world_name}'."
            )
            world_dir = os.path.join(self.server.paths.server_dir, "worlds", world_name)
            pack_folder_name = f"{pack_type}_packs"
            world_json_path = os.path.join(world_dir, f"world_{pack_folder_name}.json")
            json_filename_basename = os.path.basename(world_json_path)
            if not await aiofiles.ospath.exists(world_json_path):
                raise AppFileNotFoundError(
                    world_json_path,
                    f"Activation file '{json_filename_basename}' not found.",
                )
            packs_list = await self._read_world_activation_json(world_json_path)
            if not packs_list:
                raise UserInputError(
                    f"No {pack_type} packs are currently enabled for world '{world_name}'."
                )
            found = False
            for i, existing_pack_entry in enumerate(packs_list):
                if (
                    isinstance(existing_pack_entry, dict)
                    and existing_pack_entry.get("pack_id") == pack_uuid
                ):
                    packs_list[i]["subpack"] = subpack_name
                    found = True
                    break
            if not found:
                raise UserInputError(
                    f"Pack '{pack_uuid}' is not currently active. You must enable it first."
                )
            try:
                lock = self.server.get_file_lock(world_json_path)
                async with lock:
                    await save_json(packs_list, world_json_path, indent=2)
                self.server.logger.debug(
                    f"Successfully wrote updated subpack '{subpack_name}' to '{json_filename_basename}'."
                )
            except OSError as e:
                raise FileOperationError(
                    f"Failed to write world pack JSON '{json_filename_basename}': {e}"
                ) from e

    async def disable_addon(
        self, pack_uuid: str, pack_type: str, world_name: Optional[str] = None
    ) -> None:
        """Disables an addon by removing it from the world's activation list asynchronously, preserving files.

        Args:
            pack_uuid (str): The UUID of the pack to disable.
            pack_type (str): The type of pack; must be either ``"behavior"`` or ``"resource"``.
            world_name (Optional[str]): The name of the world.
        """
        async with self.server.operation_lock:
            if not pack_uuid or not pack_type:
                raise MissingArgumentError("Pack UUID and pack type are required.")
            if pack_type not in ("behavior", "resource"):
                raise UserInputError("Pack type must be 'behavior' or 'resource'.")
            if world_name is None:
                world_name = await self.server.get_world_name()
            self.server.logger.info(
                f"Disabling {pack_type} pack '{pack_uuid}' in world '{world_name}'."
            )
            world_dir = os.path.join(self.server.paths.server_dir, "worlds", world_name)
            pack_folder_name = f"{pack_type}_packs"
            world_json_path = os.path.join(world_dir, f"world_{pack_folder_name}.json")
            await self._remove_pack_from_world_json(world_json_path, pack_uuid)

    async def reorder_addons(
        self, uuids: List[str], pack_type: str, world_name: Optional[str] = None
    ) -> None:
        """Reorders the active addons based on a provided list of UUIDs asynchronously.

        This method strictly verifies that the provided list of UUIDs contains
        the exact same set of active UUIDs.

        Args:
            uuids (List[str]): The exact active UUIDs in their new order.
            pack_type (str): The type of pack; must be either ``"behavior"`` or ``"resource"``.
            world_name (Optional[str]): The name of the world.
        """
        async with self.server.operation_lock:
            if not uuids or not pack_type:
                raise MissingArgumentError("UUID list and pack type are required.")
            if pack_type not in ("behavior", "resource"):
                raise UserInputError("Pack type must be 'behavior' or 'resource'.")
            if world_name is None:
                world_name = await self.server.get_world_name()
            self.server.logger.info(
                f"Reordering {pack_type} packs in world '{world_name}'."
            )
            world_dir = os.path.join(self.server.paths.server_dir, "worlds", world_name)
            pack_folder_name = f"{pack_type}_packs"
            world_json_path = os.path.join(world_dir, f"world_{pack_folder_name}.json")
            original_packs_list = await self._read_world_activation_json(
                world_json_path
            )
            original_uuids = [
                p.get("pack_id") for p in original_packs_list if p.get("pack_id")
            ]
            if set(uuids) != set(original_uuids):
                raise UserInputError(
                    "The provided UUID list does not contain the exact same set of active UUIDs. Disabling/Enabling must be done via their respective endpoints."
                )
            if len(uuids) != len(original_uuids):
                raise UserInputError("The provided UUID list contains duplicates.")
            pack_map = {
                p.get("pack_id"): p for p in original_packs_list if p.get("pack_id")
            }
            new_packs_list = [pack_map[uuid] for uuid in uuids]
            try:
                lock = self.server.get_file_lock(world_json_path)
                async with lock:
                    await save_json(new_packs_list, world_json_path, indent=2)
                self.server.logger.info(
                    f"Successfully reordered {pack_type} packs in world '{world_name}'."
                )
            except OSError as e:
                raise FileOperationError(
                    f"Failed to write reordered activation file: {e}"
                ) from e

    async def export_addon(
        self,
        pack_uuid: str,
        pack_type: str,
        export_dir: str,
        world_name: Optional[str] = None,
    ) -> str:
        """Exports a specific installed addon from a world into a ``.mcpack`` file asynchronously.

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
                :meth:`~.core.bedrock_server.BedrockServer.get_world_name`
                are unavailable when ``world_name`` is ``None``.
        """
        async with self.server.operation_lock:
            if not pack_uuid or not pack_type or (not export_dir):
                raise MissingArgumentError(
                    "Pack UUID, pack type, and export directory are required."
                )
            if pack_type not in ("behavior", "resource"):
                raise UserInputError("Pack type must be 'behavior' or 'resource'.")
            if world_name is None:
                world_name = await self.server.get_world_name()
            self.server.logger.info(
                f"Exporting {pack_type} pack '{pack_uuid}' from world '{world_name}'."
            )
            world_dir = os.path.join(self.server.paths.server_dir, "worlds", world_name)
            pack_folder_name = f"{pack_type}_packs"
            physical_packs = await self._scan_physical_packs(
                world_dir, pack_folder_name
            )
            target_pack = next(
                (p for p in physical_packs if p["uuid"] == pack_uuid), None
            )
            if not target_pack:
                raise AppFileNotFoundError(
                    f"pack with UUID {pack_uuid}",
                    f"{pack_folder_name} in world '{world_name}'",
                )
            pack_name = target_pack["name"]
            pack_version = ".".join(map(str, target_pack["version"]))
            pack_source_path = target_pack["path"]
            safe_pack_name = re.sub('[<>:"/\\\\|?* ]', "_", pack_name)
            export_filename = f"{safe_pack_name}_{pack_version}.mcpack"
            export_file_path = os.path.join(export_dir, export_filename)
            await run_in_thread(os.makedirs, export_dir, exist_ok=True)
            try:
                self.server.logger.debug(
                    f"Zipping '{pack_source_path}' to '{export_file_path}'"
                )

                def _do_export():
                    with zipfile.ZipFile(
                        export_file_path, "w", zipfile.ZIP_DEFLATED
                    ) as zipf:
                        for root, _dirs, files in os.walk(pack_source_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                archive_name = os.path.relpath(
                                    file_path, pack_source_path
                                )
                                zipf.write(file_path, archive_name)

                await run_in_thread(_do_export)
                self.server.logger.info(
                    f"Successfully exported addon '{pack_name}' to '{export_file_path}'."
                )
                return export_file_path
            except (OSError, zipfile.BadZipFile) as e:
                raise FileOperationError(
                    f"Could not create addon archive for '{pack_name}': {e}"
                ) from e

    async def remove_addon(
        self, pack_uuid: str, pack_type: str, world_name: Optional[str] = None
    ) -> None:
        """Removes a specific addon from a world asynchronously.

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
                :meth:`~.core.bedrock_server.BedrockServer.get_world_name`
                are unavailable when ``world_name`` is ``None``.
        """
        async with self.server.operation_lock:
            if not pack_uuid or not pack_type:
                raise MissingArgumentError("Pack UUID and pack type are required.")
            if pack_type not in ("behavior", "resource"):
                raise UserInputError("Pack type must be 'behavior' or 'resource'.")
            if world_name is None:
                world_name = await self.server.get_world_name()
            self.server.logger.info(
                f"Removing {pack_type} pack '{pack_uuid}' from world '{world_name}'."
            )
            world_dir = os.path.join(self.server.paths.server_dir, "worlds", world_name)
            pack_folder_name = f"{pack_type}_packs"
            physical_packs = await self._scan_physical_packs(
                world_dir, pack_folder_name
            )
            target_pack = next(
                (p for p in physical_packs if p["uuid"] == pack_uuid), None
            )
            if not target_pack:
                self.server.logger.warning(
                    f"Pack files for UUID '{pack_uuid}' not found. Attempting to clean activation JSON."
                )
            else:
                pack_name = target_pack["name"]
                pack_source_path = target_pack["path"]
                try:
                    self.server.logger.debug(
                        f"Deleting pack folder: {pack_source_path}"
                    )
                    await run_in_thread(shutil.rmtree, pack_source_path)
                    self.server.logger.info(
                        f"Successfully deleted files for pack '{pack_name}'."
                    )
                except OSError as e:
                    raise FileOperationError(
                        f"Failed to delete addon folder for '{pack_name}': {e}"
                    ) from e
            world_json_path = os.path.join(world_dir, f"world_{pack_folder_name}.json")
            await self._remove_pack_from_world_json(world_json_path, pack_uuid)

    async def _process_mcaddon_archive(self, mcaddon_file_path: str) -> None:
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
        self.server.logger.info(
            f"Server '{self.server.server_name}': Processing .mcaddon '{os.path.basename(mcaddon_file_path)}'."
        )
        async with temporary_directory() as temporary:
            temp_dir = str(temporary)
            try:
                self.server.logger.info(
                    f"Extracting '{os.path.basename(mcaddon_file_path)}' to temp dir..."
                )

                def _extract():
                    with zipfile.ZipFile(mcaddon_file_path, "r") as zip_ref:
                        extract_archive(zip_ref, temp_dir)

                await run_in_thread(_extract)
                self.server.logger.debug(
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
            await self._process_extracted_mcaddon_contents(temp_dir)

    async def _process_extracted_mcaddon_contents(
        self, temp_dir_with_extracted_files: str
    ) -> None:
        """Processes ``.mcworld`` and ``.mcpack`` files from an extracted ``.mcaddon`` archive.

        This method iterates through the files within the provided temporary directory
        (which contains the extracted contents of an ``.mcaddon`` file).
        It identifies and processes:

            - ``.mcworld`` files: These are processed by calling
              :meth:`~.core.server.world.ServerWorlds.extract_mcworld`,
              effectively importing the world template into the server's active world.
              Requires :meth:`~.core.bedrock_server.BedrockServer.get_world_name`
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
                :meth:`~.core.server.world.ServerWorlds.extract_mcworld`
                or :meth:`._process_mcpack_archive`.
            AttributeError: If required methods from other mixins, such as
                :meth:`~.core.bedrock_server.BedrockServer.get_world_name` or
                :meth:`~.core.server.world.ServerWorlds.extract_mcworld`,
                are not available on the server instance.
        """
        self.server.logger.debug(
            f"Server '{self.server.server_name}': Processing extracted .mcaddon contents in '{temp_dir_with_extracted_files}'."
        )
        mcworld_files_found = await run_in_thread(
            glob.glob, os.path.join(temp_dir_with_extracted_files, "*.mcworld")
        )
        if mcworld_files_found:
            self.server.logger.info(
                f"Found {len(mcworld_files_found)} .mcworld file(s) in .mcaddon."
            )
            active_world_name = await self.server.get_world_name()
            for world_file_path in mcworld_files_found:
                world_filename_basename = os.path.basename(world_file_path)
                self.server.logger.info(
                    f"Processing extracted world file: '{world_filename_basename}' into active world '{active_world_name}'."
                )
                try:
                    await self.server.worlds.extract_mcworld(
                        world_file_path, active_world_name
                    )
                    self.server.logger.info(
                        f"Successfully processed '{world_filename_basename}' into world '{active_world_name}'."
                    )
                except Exception as e:
                    raise FileOperationError(
                        f"Failed processing world '{world_filename_basename}' from .mcaddon for server '{self.server.server_name}': {e}"
                    ) from e
        mcpack_files_found = await run_in_thread(
            glob.glob, os.path.join(temp_dir_with_extracted_files, "*.mcpack")
        )
        if mcpack_files_found:
            self.server.logger.info(
                f"Found {len(mcpack_files_found)} .mcpack file(s) in .mcaddon."
            )
            for pack_file_path in mcpack_files_found:
                pack_filename_basename = os.path.basename(pack_file_path)
                self.server.logger.info(
                    f"Processing extracted pack file: '{pack_filename_basename}'."
                )
                try:
                    await self._process_mcpack_archive(pack_file_path)
                except Exception as e:
                    raise FileOperationError(
                        f"Failed processing pack '{pack_filename_basename}' from .mcaddon for server '{self.server.server_name}': {e}"
                    ) from e
        found_pack_folders = []
        for item in await run_in_thread(os.listdir, temp_dir_with_extracted_files):
            item_path = os.path.join(temp_dir_with_extracted_files, item)
            if await aiofiles.ospath.isdir(item_path) and await aiofiles.ospath.isfile(
                os.path.join(item_path, "manifest.json")
            ):
                found_pack_folders.append(item_path)
        if found_pack_folders:
            self.server.logger.info(
                f"Found {len(found_pack_folders)} pack folder(s) in .mcaddon."
            )
            for pack_folder_path in found_pack_folders:
                folder_name = os.path.basename(pack_folder_path)
                self.server.logger.info(
                    f"Processing extracted pack folder: '{folder_name}'."
                )
                try:
                    await self._install_pack_from_extracted_data(
                        pack_folder_path, pack_folder_path
                    )
                except Exception as e:
                    raise FileOperationError(
                        f"Failed processing pack folder '{folder_name}' from .mcaddon for server '{self.server.server_name}': {e}"
                    ) from e
        if (
            not mcworld_files_found
            and (not mcpack_files_found)
            and (not found_pack_folders)
        ):
            self.server.logger.warning(
                f"No .mcworld, .mcpack files, or pack folders found in extracted .mcaddon at '{temp_dir_with_extracted_files}'."
            )

    async def _process_mcpack_archive(self, mcpack_file_path: str) -> None:
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
        self.server.logger.info(
            f"Server '{self.server.server_name}': Processing .mcpack '{mcpack_filename}'."
        )
        async with temporary_directory() as temporary:
            temp_dir = str(temporary)
            try:
                self.server.logger.info(
                    f"Extracting '{mcpack_filename}' to temp dir..."
                )

                def _extract():
                    with zipfile.ZipFile(mcpack_file_path, "r") as zip_ref:
                        extract_archive(zip_ref, temp_dir)

                await run_in_thread(_extract)
                self.server.logger.debug(f"Successfully extracted '{mcpack_filename}'.")
            except zipfile.BadZipFile as e:
                raise ExtractError(
                    f"Invalid .mcpack (not a zip file): {mcpack_filename}"
                ) from e
            except OSError as e:
                raise FileOperationError(
                    f"Error extracting '{mcpack_filename}': {e}"
                ) from e
            install_source_dir = temp_dir
            if not os.path.isfile(os.path.join(temp_dir, "manifest.json")):
                entries = os.listdir(temp_dir)
                if len(entries) == 1 and os.path.isdir(
                    os.path.join(temp_dir, entries[0])
                ):
                    potential_nested_dir = os.path.join(temp_dir, entries[0])
                    if os.path.isfile(
                        os.path.join(potential_nested_dir, "manifest.json")
                    ):
                        self.server.logger.info(
                            f"Detected nested pack directory: '{entries[0]}'. Adjusting source."
                        )
                        install_source_dir = potential_nested_dir
            await self._install_pack_from_extracted_data(
                install_source_dir, mcpack_file_path
            )

    async def _install_pack_from_extracted_data(
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
               Requires :meth:`~.core.bedrock_server.BedrockServer.get_world_name`.
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
            AttributeError: If :meth:`~.core.bedrock_server.BedrockServer.get_world_name`
                is not available.
        """
        original_mcpack_filename = os.path.basename(original_mcpack_path)
        self.server.logger.debug(
            f"Server '{self.server.server_name}': Processing manifest for pack from '{original_mcpack_filename}' in '{extracted_pack_dir}'."
        )
        try:
            manifest = await self._extract_manifest_info(extracted_pack_dir)
            pack_type = manifest.pack_type
            uuid = manifest.header.uuid
            version_list = manifest.header.version
            addon_name = manifest.header.name
            self.server.logger.info(
                f"Manifest for '{original_mcpack_filename}': Type='{pack_type}', UUID='{uuid}', Version='{version_list}', Name='{addon_name}'"
            )
            active_world_name = await self.server.get_world_name()
            active_world_dir = os.path.join(
                self.server.paths.server_dir, "worlds", active_world_name
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
            await run_in_thread(os.makedirs, behavior_packs_target_base, exist_ok=True)
            await run_in_thread(os.makedirs, resource_packs_target_base, exist_ok=True)
            version_str = ".".join(map(str, version_list))
            actual_folder_name = addon_name
            if actual_folder_name == "pack.name" and original_mcpack_filename:
                actual_folder_name = os.path.splitext(original_mcpack_filename)[0]
            safe_addon_folder_name = (
                re.sub('[<>:"/\\\\|?*]', "_", actual_folder_name) + f"_{version_str}"
            )
            target_install_path: str
            target_world_json_file: str
            pack_type_friendly_name: str
            if pack_type in ("data", "script"):
                target_install_path = os.path.join(
                    behavior_packs_target_base, safe_addon_folder_name
                )
                target_world_json_file = world_behavior_packs_json
                pack_type_friendly_name = "behavior"
                pack_folder_name = "behavior_packs"
            elif pack_type == "resources":
                target_install_path = os.path.join(
                    resource_packs_target_base, safe_addon_folder_name
                )
                target_world_json_file = world_resource_packs_json
                pack_type_friendly_name = "resource"
                pack_folder_name = "resource_packs"
            else:
                raise UserInputError(
                    f"Cannot install unknown pack type: '{pack_type}' for '{original_mcpack_filename}'"
                )
            self.server.logger.info(
                f"Installing {pack_type_friendly_name} pack '{addon_name}' v{version_str} into: {target_install_path}"
            )
            existing_physical_packs = await self._scan_physical_packs(
                active_world_dir, pack_folder_name
            )
            async with temporary_directory(active_world_dir) as staging:
                staged_pack = staging / "pack"
                await run_in_thread(shutil.copytree, extracted_pack_dir, staged_pack)
                async with file_transaction(active_world_dir) as transaction:
                    for existing_pack in existing_physical_packs:
                        if (
                            existing_pack["uuid"] == uuid
                            and existing_pack["path"] != target_install_path
                        ):
                            await run_in_thread(
                                transaction.retire, Path(existing_pack["path"])
                            )
                    await run_in_thread(
                        transaction.replace, staged_pack, Path(target_install_path)
                    )
                    await run_in_thread(transaction.watch, Path(target_world_json_file))
                    await self._update_world_pack_json_file(
                        target_world_json_file, uuid, version_list
                    )
            self.server.logger.info(
                f"Successfully installed and activated {pack_type_friendly_name} pack '{addon_name}' v{version_str} for server '{self.server.server_name}'."
            )
        except (AppFileNotFoundError, ConfigParseError) as e_manifest:
            self.server.logger.error(
                f"Failed to process manifest for '{original_mcpack_filename}': {e_manifest}",
                exc_info=True,
            )
            raise
        except (FileOperationError, UserInputError, AppFileNotFoundError) as e_install:
            self.server.logger.error(
                f"Failed to install pack from '{original_mcpack_filename}': {e_install}",
                exc_info=True,
            )
            raise
        except Exception as e_unexp:
            self.server.logger.error(
                f"Unexpected error installing pack '{original_mcpack_filename}': {e_unexp}",
                exc_info=True,
            )
            raise FileOperationError(
                f"Unexpected error processing pack '{original_mcpack_filename}' for server '{self.server.server_name}': {e_unexp}"
            ) from e_unexp

    async def _extract_manifest_info(self, extracted_pack_dir: str) -> PackManifest:
        """Read and validate normalized metadata from a pack manifest."""
        manifest_file = os.path.join(extracted_pack_dir, "manifest.json")
        if not await aiofiles.ospath.isfile(manifest_file):
            raise AppFileNotFoundError(manifest_file, "Manifest file")
        try:
            async with aiofiles.open(manifest_file, "r", encoding="utf-8") as source:
                return PackManifest.model_validate_json(await source.read())
        except ValueError as error:
            raise ConfigParseError(
                f"Invalid manifest '{manifest_file}': {error}"
            ) from error
        except OSError as error:
            raise FileOperationError(
                f"Cannot read manifest '{manifest_file}': {error}"
            ) from error

    async def _update_world_pack_json_file(
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
        self.server.logger.debug(
            f"Updating world pack JSON '{json_filename_basename}' for UUID: {pack_uuid}, Version: {pack_version_list}"
        )
        packs_list = []
        try:
            if await aiofiles.ospath.exists(world_json_file_path):
                async with aiofiles.open(
                    world_json_file_path, "r", encoding="utf-8"
                ) as f:
                    content = await f.read()
                    if content.strip():
                        loaded_packs = json.loads(content)
                        if isinstance(loaded_packs, list):
                            packs_list = loaded_packs
                        else:
                            self.server.logger.warning(
                                f"'{json_filename_basename}' content not a list. Will overwrite."
                            )
        except ValueError as e:
            self.server.logger.warning(
                f"Invalid JSON in '{json_filename_basename}'. Will overwrite. Error: {e}"
            )
        except OSError as e:
            raise FileOperationError(
                f"Failed to read world pack JSON '{json_filename_basename}': {e}"
            ) from e
        pack_entry_found = False
        input_version_tuple = tuple(pack_version_list)
        for i, existing_pack_entry in enumerate(packs_list):
            if (
                isinstance(existing_pack_entry, dict)
                and existing_pack_entry.get("pack_id") == pack_uuid
            ):
                pack_entry_found = True
                existing_version_list = existing_pack_entry.get("version")
                if (
                    isinstance(existing_version_list, list)
                    and len(existing_version_list) == 3
                ):
                    existing_version_tuple = tuple(existing_version_list)
                    if input_version_tuple != existing_version_tuple:
                        if input_version_tuple > existing_version_tuple:
                            self.server.logger.info(
                                f"Updating pack '{pack_uuid}' in '{json_filename_basename}' from v{existing_version_list} to v{pack_version_list}."
                            )
                        elif input_version_tuple < existing_version_tuple:
                            self.server.logger.warning(
                                f"Downgrading pack '{pack_uuid}' in '{json_filename_basename}' from v{existing_version_list} to v{pack_version_list}."
                            )
                            self.server.logger.warning(
                                "Downgrading packs can cause compatibility issues or data loss."
                            )
                        packs_list[i] = {
                            "pack_id": pack_uuid,
                            "version": pack_version_list,
                        }
                else:
                    self.server.logger.warning(
                        f"Pack '{pack_uuid}' in '{json_filename_basename}' has invalid version. Overwriting with v{pack_version_list}."
                    )
                    packs_list[i] = {"pack_id": pack_uuid, "version": pack_version_list}
                break
        if not pack_entry_found:
            self.server.logger.info(
                f"Adding new pack '{pack_uuid}' v{pack_version_list} to '{json_filename_basename}'."
            )
            packs_list.append({"pack_id": pack_uuid, "version": pack_version_list})
        try:
            await run_in_thread(
                os.makedirs, os.path.dirname(world_json_file_path), exist_ok=True
            )
            lock = self.server.get_file_lock(world_json_file_path)
            async with lock:
                await save_json(packs_list, world_json_file_path, indent=2)
            self.server.logger.debug(
                f"Successfully wrote updated packs to '{json_filename_basename}'."
            )
        except OSError as e:
            raise FileOperationError(
                f"Failed to write world pack JSON '{json_filename_basename}': {e}"
            ) from e

    async def _scan_physical_packs(
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
        if not await aiofiles.ospath.isdir(pack_base_dir):
            return []
        installed_packs = []
        for pack_dir_name in await run_in_thread(os.listdir, pack_base_dir):
            pack_full_path = os.path.join(pack_base_dir, pack_dir_name)
            if os.path.isdir(pack_full_path):
                try:
                    manifest = await self._extract_manifest_info(pack_full_path)
                    uuid = manifest.header.uuid
                    version = manifest.header.version
                    name = manifest.header.name
                    subpacks = [
                        item.model_dump(mode="json", exclude_unset=True)
                        for item in manifest.subpacks
                    ]
                    if name == "pack.name":
                        version_str = f"_{'.'.join(map(str, version))}"
                        if pack_dir_name.endswith(version_str):
                            name = pack_dir_name[: -len(version_str)]
                        else:
                            name = pack_dir_name
                    installed_packs.append(
                        {
                            "name": name,
                            "uuid": uuid,
                            "version": version,
                            "path": pack_full_path,
                            "subpacks": subpacks,
                        }
                    )
                except (AppFileNotFoundError, ConfigParseError) as e:
                    self.server.logger.warning(
                        f"Could not read manifest for pack in '{pack_full_path}'. Skipping. Reason: {e}"
                    )
        return installed_packs

    async def _read_world_activation_json(
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
        if not await aiofiles.ospath.exists(world_json_file_path):
            return []
        try:
            data = await load_json(world_json_file_path)
            if data is None:
                return []
            if isinstance(data, list):
                return data
            else:
                self.server.logger.warning(
                    f"File '{world_json_file_path}' does not contain a JSON list. Treating as empty."
                )
                return []
        except (ValueError, OSError) as e:
            self.server.logger.error(
                f"Failed to read or parse '{world_json_file_path}': {e}"
            )
            return []

    async def _compare_physical_and_activated(
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
        for p_pack in physical:
            status = "ACTIVE" if p_pack["uuid"] in activated_uuids else "INACTIVE"
            pack_info = {
                "name": p_pack["name"],
                "uuid": p_pack["uuid"],
                "version": p_pack["version"],
                "status": status,
                "subpacks": p_pack.get("subpacks", []),
                "path": p_pack.get("path"),
            }
            if status == "ACTIVE":
                entry = next(
                    (a for a in activated if a.get("pack_id") == p_pack["uuid"]), None
                )
                if entry and "subpack" in entry:
                    pack_info["active_subpack"] = entry["subpack"]
            results.append(pack_info)
        physical_uuids = {p["uuid"] for p in physical}
        orphaned_uuids = activated_uuids - physical_uuids
        for orphan_uuid in orphaned_uuids:
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
        activated_order = [
            entry["pack_id"] for entry in activated if "pack_id" in entry
        ]
        active_packs = []
        for uuid in activated_order:
            found = next((r for r in results if r["uuid"] == uuid), None)
            if found:
                active_packs.append(found)
        inactive_packs = [r for r in results if r["status"] != "ACTIVE"]
        inactive_packs_sorted = sorted(inactive_packs, key=lambda x: x["name"])
        return active_packs + inactive_packs_sorted

    async def _remove_pack_from_world_json(
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
        if not await aiofiles.ospath.exists(world_json_file_path):
            self.server.logger.debug(
                f"Activation file '{json_filename}' not found. Nothing to remove."
            )
            return
        original_packs_list = await self._read_world_activation_json(
            world_json_file_path
        )
        if not original_packs_list:
            return
        updated_packs_list = [
            p for p in original_packs_list if p.get("pack_id") != pack_uuid
        ]
        if len(original_packs_list) == len(updated_packs_list):
            self.server.logger.debug(
                f"Pack UUID '{pack_uuid}' not found in '{json_filename}'. No changes made."
            )
            return
        try:
            lock = self.server.get_file_lock(world_json_file_path)
            async with lock:
                await save_json(updated_packs_list, world_json_file_path, indent=2)
            self.server.logger.info(
                f"Removed pack '{pack_uuid}' from activation file '{json_filename}'."
            )
        except OSError as e:
            raise FileOperationError(
                f"Failed to write updated activation file '{json_filename}': {e}"
            ) from e
