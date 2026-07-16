import click
import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.utils import handle_api_response


@pytest.fixture
def runner():
    return CliRunner()


def test_handle_api_response_success(runner):
    """Test handle_api_response correctly outputs custom success message."""
    # Success response
    response = {
        "status": "success",
        "message": "My custom success msg",
        "data": {"foo": "bar"},
    }

    # We need a context or simple function to catch the echo since handle_api_response uses click.secho
    def call_helper():
        return handle_api_response(response, "Default success msg")

    @click.command()
    def dummy_cmd():
        data = call_helper()
        click.echo(f"Data: {data['foo']}")

    result = runner.invoke(dummy_cmd)
    assert result.exit_code == 0
    assert "Success: My custom success msg" in result.output
    assert "Data: bar" in result.output


def test_handle_api_response_success_default_msg(runner):
    """Test handle_api_response correctly outputs default success message when custom is missing."""
    response = {"status": "success", "data": {"foo": "bar"}}

    @click.command()
    def dummy_cmd():
        handle_api_response(response, "Default success msg")

    result = runner.invoke(dummy_cmd)
    assert result.exit_code == 0
    assert "Success: Default success msg" in result.output


def test_handle_api_response_error(runner):
    """Test handle_api_response raises an abort and prints the error message."""
    response = {"status": "error", "message": "Something went wrong"}

    @click.command()
    def dummy_cmd():
        handle_api_response(response, "Default success msg")

    result = runner.invoke(dummy_cmd)
    assert result.exit_code == 1  # Abort
    assert "Error: Something went wrong" in result.output


def test_handle_api_response_error_no_msg(runner):
    """Test handle_api_response raises an abort and prints a generic message when missing."""
    response = {"status": "error"}

    @click.command()
    def dummy_cmd():
        handle_api_response(response, "Default success msg")

    result = runner.invoke(dummy_cmd)
    assert result.exit_code == 1  # Abort
    assert "Error: An unknown error occurred." in result.output
