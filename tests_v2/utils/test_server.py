from unittest.mock import MagicMock

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
    "valid_name",
    [
        "server-1",
        "my_server",
        "TestServer123",
    ],
)
def test_core_validate_server_name_format_valid(valid_name):
    """Test core_validate_server_name_format silently accepts valid server names."""
    core_validate_server_name_format(valid_name)  # Should not raise


@pytest.mark.parametrize("invalid_name", ["", "my server", "server@123", "test/server"])
def test_core_validate_server_name_format_invalid(invalid_name):
    """Test core_validate_server_name_format correctly rejects invalid server names."""
    with pytest.raises(InvalidServerNameError):
        core_validate_server_name_format(invalid_name)


def test_validate_server_success(app_context, monkeypatch):
    """Test validate_server returns True for correctly mocked installed servers."""
    server = MagicMock()
    server.is_installed.return_value = True
    monkeypatch.setattr(app_context, "get_server", lambda x: server)

    assert validate_server("test_server", app_context) is True


def test_validate_server_empty_name(app_context):
    """Test validate_server rejects empty server names."""
    with pytest.raises(MissingArgumentError):
        validate_server("", app_context)


def test_validate_server_not_installed(app_context, monkeypatch):
    """Test validate_server returns False if the server class returns false."""
    server = MagicMock()
    server.is_installed.return_value = False
    monkeypatch.setattr(app_context, "get_server", lambda x: server)

    assert validate_server("test_server", app_context) is False


def test_validate_server_exception_caught(app_context, monkeypatch):
    """Test validate_server catches inner application exceptions returning False."""

    def raise_error(name):
        raise InvalidServerNameError("Bad format")

    monkeypatch.setattr(app_context, "get_server", raise_error)
    assert validate_server("bad_name!", app_context) is False


def test_get_servers_data_success(app_context, real_bedrock_server):
    """Test get_servers_data returns mapped details successfully retrieving from standard configs."""
    # Setup real_bedrock_server correctly mock its validation
    # Actually real_bedrock_server fixture creates valid dummy files!

    # We just need to make sure the server base dir exists and holds the dummy server
    servers_data, error_messages = get_servers_data(app_context)

    assert len(error_messages) == 0
    assert len(servers_data) == 1
    assert servers_data[0]["name"] == "test_server"
    assert "status" in servers_data[0]


def test_get_servers_data_base_dir_missing(app_context, tmp_path):
    """Test get_servers_data fails cleanly throwing an AppFileNotFoundError."""
    app_context.settings.set("paths.servers", str(tmp_path / "missing_dir"))

    with pytest.raises(AppFileNotFoundError) as exc_info:
        get_servers_data(app_context)
    assert "Server base directory not found at path" in str(exc_info.value)


def test_get_servers_data_not_installed(app_context, tmp_path):
    """Test get_servers_data skips directories representing uninstalled servers."""
    # Setup dummy directory that is NOT a valid server
    base_dir = tmp_path / "servers"
    base_dir.mkdir()
    (base_dir / "invalid_server").mkdir()

    app_context.settings.set("paths.servers", str(base_dir))

    servers_data, error_messages = get_servers_data(app_context)

    assert len(servers_data) == 0
    assert len(error_messages) == 0


def test_get_servers_data_exception_on_server(
    app_context, real_bedrock_server, monkeypatch
):
    """Test get_servers_data handles exception safely on corrupted specific server instances."""

    def mock_get_server(name):
        raise ConfigurationError("Some bad config")

    from bedrock_server_manager.error import ConfigurationError

    monkeypatch.setattr(app_context, "get_server", mock_get_server)

    servers_data, error_messages = get_servers_data(app_context)

    assert len(servers_data) == 0
    assert len(error_messages) == 1
    assert "Could not get info for server" in error_messages[0]
