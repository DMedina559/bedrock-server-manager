import pytest
import os
import shutil
import zipfile
import tempfile
import json
from bedrock_server_manager.core.server.addon_mixin import ServerAddonMixin
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.config.settings import Settings


class SetupBedrockServer(ServerAddonMixin, BedrockServerBaseMixin):
    def get_world_name(self):
        return "Bedrock level"


@pytest.fixture
def addon_mixin_fixture():
    temp_dir = tempfile.mkdtemp()
    server_name = "test_server"
    settings = Settings()
    settings.set("paths.servers", os.path.join(temp_dir, "servers"))

    server = SetupBedrockServer(server_name=server_name, settings_instance=settings)
    os.makedirs(server.server_dir, exist_ok=True)
    os.makedirs(
        os.path.join(server.server_dir, "development_resource_packs"), exist_ok=True
    )
    os.makedirs(
        os.path.join(server.server_dir, "development_behavior_packs"), exist_ok=True
    )
    os.makedirs(os.path.join(server.server_dir, "resource_packs"), exist_ok=True)
    os.makedirs(os.path.join(server.server_dir, "behavior_packs"), exist_ok=True)

    yield server, temp_dir

    shutil.rmtree(temp_dir)


def test_list_world_addons(addon_mixin_fixture):
    server, _ = addon_mixin_fixture

    # Create dummy addons
    world_dir = os.path.join(server.server_dir, "worlds", "Bedrock level")
    os.makedirs(os.path.join(world_dir, "resource_packs", "rp1_folder"), exist_ok=True)
    with open(
        os.path.join(world_dir, "resource_packs", "rp1_folder", "manifest.json"), "w"
    ) as f:
        json.dump(
            {
                "header": {"name": "rp1", "uuid": "rp1_uuid", "version": [1, 0, 0]},
                "modules": [{"type": "resources"}],
            },
            f,
        )

    with open(os.path.join(world_dir, "world_resource_packs.json"), "w") as f:
        json.dump([{"pack_id": "rp1_uuid", "version": [1, 0, 0]}], f)

    addons = server.list_world_addons()

    assert len(addons["resource_packs"]) == 1
    assert addons["resource_packs"][0]["uuid"] == "rp1_uuid"
    assert addons["resource_packs"][0]["status"] == "ACTIVE"


from unittest.mock import patch


from bedrock_server_manager.error import (
    UserInputError,
    ExtractError,
    AppFileNotFoundError,
)


def test_process_addon_file(addon_mixin_fixture):
    server, temp_dir = addon_mixin_fixture

    # Create a dummy addon file
    addon_path = os.path.join(temp_dir, "test_addon.mcpack")
    with zipfile.ZipFile(addon_path, "w") as zf:
        zf.writestr(
            "manifest.json",
            '{"header": {"name": "test addon", "uuid": "rp1", "version": [1,0,0]}, "modules": [{"type": "resources"}]}',
        )

    with patch.object(server, "get_world_name", return_value="Bedrock level"):
        server.process_addon_file(addon_path)

    assert len(server.list_world_addons()["resource_packs"]) == 1


def test_process_addon_file_unsupported_type(addon_mixin_fixture):
    server, temp_dir = addon_mixin_fixture
    unsupported_path = os.path.join(temp_dir, "test.txt")
    with open(unsupported_path, "w") as f:
        f.write("test")
    with pytest.raises(UserInputError):
        server.process_addon_file(unsupported_path)


def test_process_mcaddon_archive_invalid_zip(addon_mixin_fixture):
    server, temp_dir = addon_mixin_fixture
    invalid_zip_path = os.path.join(temp_dir, "invalid.mcaddon")
    with open(invalid_zip_path, "w") as f:
        f.write("not a zip")
    with pytest.raises(ExtractError):
        server._process_mcaddon_archive(invalid_zip_path)


def test_install_pack_from_extracted_data_missing_manifest(addon_mixin_fixture):
    server, temp_dir = addon_mixin_fixture
    pack_dir = os.path.join(temp_dir, "pack")
    os.makedirs(pack_dir)
    with pytest.raises(AppFileNotFoundError):
        server._install_pack_from_extracted_data(pack_dir, "dummy.mcpack")


def test_remove_addon_not_found(addon_mixin_fixture):
    server, _ = addon_mixin_fixture
    world_dir = os.path.join(server.server_dir, "worlds", "Bedrock level")
    os.makedirs(world_dir, exist_ok=True)
    # No exception should be raised
    server.remove_addon("non_existent_uuid", "resource")


def test_export_addon_not_found(addon_mixin_fixture):
    server, temp_dir = addon_mixin_fixture
    world_dir = os.path.join(server.server_dir, "worlds", "Bedrock level")
    os.makedirs(world_dir, exist_ok=True)
    with pytest.raises(AppFileNotFoundError):
        server.export_addon("non_existent_uuid", "resource", temp_dir)


def test_remove_addon(addon_mixin_fixture):
    server, _ = addon_mixin_fixture

    # Create dummy addons
    world_dir = os.path.join(server.server_dir, "worlds", "Bedrock level")
    os.makedirs(world_dir, exist_ok=True)
    with open(os.path.join(world_dir, "world_resource_packs.json"), "w") as f:
        json.dump([{"pack_id": "rp1", "version": [1, 0, 0]}], f)

    addon_dir = os.path.join(
        server.server_dir,
        "worlds",
        "Bedrock level",
        "resource_packs",
        "test_addon_1.0.0",
    )
    os.makedirs(addon_dir)
    with open(os.path.join(addon_dir, "manifest.json"), "w") as f:
        json.dump(
            {
                "header": {"name": "test_addon", "uuid": "rp1", "version": [1, 0, 0]},
                "modules": [{"type": "resources"}],
            },
            f,
        )

    server.remove_addon("rp1", "resource")

    assert not os.path.exists(addon_dir)

    with open(os.path.join(world_dir, "world_resource_packs.json"), "r") as f:
        data = json.load(f)
        assert len(data) == 0
