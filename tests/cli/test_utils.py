import click
import pytest
from click.testing import CliRunner

from bedrock_server_manager.api.models.common import ActionResponse, SuccessResponse
from bedrock_server_manager.cli.utils import handle_api_response


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (
            SuccessResponse(message="My custom success msg"),
            "Success: My custom success msg",
        ),
        (SuccessResponse(), "Success: Default success msg"),
        (
            ActionResponse(status="skipped", message="Canceled by plugin"),
            "Skipped: Canceled by plugin",
        ),
    ],
)
def test_handle_api_response(response, expected):
    @click.command()
    def dummy_cmd():
        handle_api_response(response, "Default success msg")

    result = CliRunner().invoke(dummy_cmd)
    assert result.exit_code == 0
    assert expected in result.output
