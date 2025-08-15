import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from bedrock_server_manager.cli.server_properties import properties


@pytest.fixture
def runner():
    return CliRunner()


def test_properties_get_success(runner):
    """Test the 'properties get' command with a successful API response."""
    with patch(
        "bedrock_server_manager.cli.server_properties.config_api.get_server_properties_api"
    ) as mock_get_props:
        mock_get_props.return_value = {
            "status": "success",
            "properties": {"gamemode": "survival"},
        }

        result = runner.invoke(properties, ["get", "-s", "test-server"])

        assert result.exit_code == 0
        mock_get_props.assert_called_once_with("test-server")
        assert "gamemode = survival" in result.output


def test_properties_get_not_found(runner):
    """Test the 'properties get' command when the property is not found."""
    with patch(
        "bedrock_server_manager.cli.server_properties.config_api.get_server_properties_api"
    ) as mock_get_props:
        mock_get_props.return_value = {
            "status": "success",
            "properties": {"gamemode": "survival"},
        }

        result = runner.invoke(
            properties, ["get", "-s", "test-server", "-p", "not-found"]
        )

        assert result.exit_code != 0
        assert "Property 'not-found' not found" in result.output


def test_properties_set_success(runner):
    """Test the 'properties set' command with a successful API response."""
    with (
        patch(
            "bedrock_server_manager.cli.server_properties.config_api.modify_server_properties"
        ) as mock_set_props,
        patch(
            "bedrock_server_manager.cli.server_properties._handle_api_response"
        ) as mock_handle_response,
    ):
        mock_set_props.return_value = {"status": "success"}

        result = runner.invoke(
            properties, ["set", "-s", "test-server", "-p", "gamemode=creative"]
        )

        assert result.exit_code == 0
        mock_set_props.assert_called_once_with(
            "test-server", {"gamemode": "creative"}, restart_after_modify=True
        )
        mock_handle_response.assert_called_once()


def test_properties_set_invalid_format(runner):
    """Test the 'properties set' command with an invalid property format."""
    result = runner.invoke(
        properties, ["set", "-s", "test-server", "-p", "gamemode:creative"]
    )

    assert result.exit_code != 0
    assert "Invalid format 'gamemode:creative'. Use 'key=value'." in result.output


def test_interactive_properties_workflow(runner):
    """Test the interactive properties workflow."""
    with (
        patch(
            "bedrock_server_manager.cli.server_properties.config_api.get_server_properties_api"
        ) as mock_get_props,
        patch("questionary.text") as mock_text,
        patch("questionary.select") as mock_select,
        patch("questionary.confirm") as mock_confirm,
        patch(
            "bedrock_server_manager.cli.server_properties.config_api.modify_server_properties"
        ) as mock_modify,
    ):
        mock_get_props.return_value = {
            "status": "success",
            "properties": {"gamemode": "survival"},
        }
        mock_text.return_value.ask.return_value = "survival"
        mock_select.return_value.ask.return_value = "creative"
        mock_confirm.return_value.ask.return_value = True
        mock_modify.return_value = {"status": "success"}

        result = runner.invoke(properties, ["set", "-s", "test-server"])

        assert result.exit_code == 0
        mock_modify.assert_called_once()
