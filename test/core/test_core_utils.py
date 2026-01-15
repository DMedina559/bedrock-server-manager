import pytest

from bedrock_server_manager.core.utils import core_validate_server_name_format
from bedrock_server_manager.error import InvalidServerNameError


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
