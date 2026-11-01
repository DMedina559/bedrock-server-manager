import pytest

from bedrock_server_manager.error import (
    AppFileNotFoundError,
    ConfigurationError,
    InvalidServerNameError,
    MissingArgumentError,
)
from bedrock_server_manager.utils.server import (
    core_validate_server_name_format,
    get_servers_data,
    validate_server,
)


def test_core_validate_server_name_format():
    """Test core_validate_server_name_format accepts valid names and rejects invalid ones."""
    for valid_name in ("server-1", "my_server", "TestServer123"):
        core_validate_server_name_format(valid_name)

    for invalid_name in ("", "my server", "server@123", "test/server"):
        with pytest.raises(InvalidServerNameError):
            core_validate_server_name_format(invalid_name)


async def test_validate_server_and_get_servers_data(
    app_context, real_bedrock_server, tmp_path, monkeypatch
):
    """Test validate_server and get_servers_data across valid, missing, uninstalled, and error cases."""
    assert await validate_server(real_bedrock_server.server_name, app_context)

    with pytest.raises(MissingArgumentError):
        await validate_server("", app_context)

    assert not await validate_server("missing_server", app_context)
    assert not await validate_server("bad_name!", app_context)

    # get_servers_data success
    servers_data, error_messages = await get_servers_data(app_context)
    assert len(error_messages) == 0
    assert len(servers_data) == 1
    assert servers_data[0]["name"] == "test_server"
    assert "status" in servers_data[0]

    # Exception on specific server
    with monkeypatch.context() as fault:
        fault.setattr(
            app_context,
            "prepare_server",
            lambda name: (_ for _ in ()).throw(ConfigurationError("Some bad config")),
        )
        servers_data, error_messages = await get_servers_data(app_context)
        assert len(servers_data) == 0
        assert len(error_messages) == 1
        assert error_messages[0].error.code == "configuration_error"

    # Uninstalled server directory skipped
    base_dir = tmp_path / "servers_uninstalled"
    base_dir.mkdir()
    (base_dir / "invalid_server").mkdir()
    await app_context.settings.set("paths.servers", str(base_dir))
    servers_data, error_messages = await get_servers_data(app_context)
    assert len(servers_data) == 0 and len(error_messages) == 0

    # Base dir missing
    await app_context.settings.set("paths.servers", str(tmp_path / "missing_dir"))
    with pytest.raises(
        AppFileNotFoundError, match="Server base directory not found at path"
    ):
        await get_servers_data(app_context)
