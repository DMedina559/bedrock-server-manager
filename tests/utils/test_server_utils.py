import pytest

from bedrock_server_manager.error import (
    AppFileNotFoundError,
    InvalidServerNameError,
    MissingArgumentError,
)
from bedrock_server_manager.utils.server import (
    core_validate_server_name_format,
    get_servers_data,
    validate_server,
)


@pytest.mark.parametrize(
    "server_name",
    [
        "my-server",
        "my_server",
        "server123",
        "server-123",
        "server_123",
        "My-Server_123",
    ],
)
def test_core_validate_server_name_format_valid(server_name):
    """Tests that valid server names pass validation."""
    core_validate_server_name_format(server_name)


@pytest.mark.parametrize(
    "server_name",
    [
        "",
        "my server",
        "my-server!",
        "my_server?",
        "my-server/",
        "my-server\\",
    ],
)
def test_core_validate_server_name_format_invalid(server_name):
    """Tests that invalid server names raise InvalidServerNameError."""
    with pytest.raises(InvalidServerNameError):
        core_validate_server_name_format(server_name)


# --- Server Discovery & Data Aggregation ---


def test_validate_server_valid(app_context):
    """Test validate_server for a valid server."""
    assert validate_server("test_server", app_context) is True


def test_validate_server_not_installed(app_context, mocker):
    """Test validate_server for a server that is not installed."""
    mocker.patch(
        "bedrock_server_manager.core.bedrock_server.BedrockServer.is_installed",
        return_value=False,
    )
    assert validate_server("test_server", app_context) is False


def test_validate_server_instantiation_error(app_context, mocker):
    """Test validate_server when BedrockServer instantiation fails."""
    mocker.patch(
        "bedrock_server_manager.context.AppContext.get_server",
        side_effect=InvalidServerNameError("Bad name"),
    )
    assert validate_server("bad_server_name_format!", app_context) is False


def test_validate_server_empty_name(app_context):
    """Test validate_server with an empty server name."""
    with pytest.raises(
        MissingArgumentError, match="Server name cannot be empty for validation."
    ):
        validate_server("", app_context)


def test_get_servers_data_success(app_context):
    """Test get_servers_data successfully retrieves data for multiple servers."""
    servers_data, error_messages = get_servers_data(app_context=app_context)

    assert len(servers_data) == 1
    assert servers_data[0]["name"] == "test_server"
    assert servers_data[0]["status"] == "STOPPED"
    assert "version" in servers_data[0]
    assert len(error_messages) == 0


def test_get_servers_data_base_dir_not_exist(app_context, mocker):
    """Test get_servers_data if base server directory doesn't exist."""
    mocker.patch.object(
        app_context.settings, "get", return_value="/path/to/non_existent_base_servers"
    )
    mocker.patch("os.path.isdir", return_value=False)

    with pytest.raises(AppFileNotFoundError, match="Server base directory"):
        get_servers_data(app_context)


def test_get_servers_data_with_non_installed_server(app_context, mocker):
    """Test get_servers_data ignores directories that are not valid server installations."""
    # The app_context fixture creates one valid server.
    # We can mock its is_installed method to return False.
    mocker.patch(
        "bedrock_server_manager.core.bedrock_server.BedrockServer.is_installed",
        return_value=False,
    )

    servers_data, error_messages = get_servers_data(app_context=app_context)

    assert len(servers_data) == 0
    assert len(error_messages) == 0
