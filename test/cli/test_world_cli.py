import unittest
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.world import (
    export_world,
    install_world,
    reset_world,
    world,
)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_bsm():
    bsm = MagicMock()
    return bsm


@patch("bedrock_server_manager.api.world.import_world")
@patch("questionary.confirm")
def test_install_world_non_interactive(mock_confirm, mock_import_api, runner, mock_bsm):
    with runner.isolated_filesystem():
        with open("world.mcworld", "w") as f:
            f.write("dummy world")

        mock_confirm.return_value.ask.return_value = True
        mock_import_api.return_value = {"status": "success"}
        result = runner.invoke(
            install_world,
            ["--server", "test-server", "--file", "world.mcworld"],
            obj={"bsm": mock_bsm},
        )

        assert result.exit_code == 0
        assert "World 'world.mcworld' installed successfully." in result.output
        mock_import_api.assert_called_once_with(
            "test-server", unittest.mock.ANY, stop_start_server=True
        )


@patch("bedrock_server_manager.api.application.list_available_worlds_api")
@patch("bedrock_server_manager.api.world.import_world")
@patch("questionary.select")
@patch("questionary.confirm")
def test_install_world_interactive(
    mock_confirm,
    mock_select,
    mock_import_api,
    mock_list_worlds_api,
    runner,
    mock_bsm,
):
    mock_list_worlds_api.return_value = {"files": ["/path/to/world.mcworld"]}
    mock_select.return_value.ask.return_value = "world.mcworld"
    mock_confirm.return_value.ask.return_value = True
    mock_import_api.return_value = {"status": "success"}

    result = runner.invoke(
        install_world, ["--server", "test-server"], obj={"bsm": mock_bsm}
    )

    assert result.exit_code == 0
    assert "World 'world.mcworld' installed successfully." in result.output
    mock_import_api.assert_called_once_with(
        "test-server", "/path/to/world.mcworld", stop_start_server=True
    )


@patch("bedrock_server_manager.api.world.export_world")
def test_export_world(mock_export_api, runner, mock_bsm):
    mock_export_api.return_value = {"status": "success"}
    result = runner.invoke(
        export_world, ["--server", "test-server"], obj={"bsm": mock_bsm}
    )

    assert result.exit_code == 0
    assert "World exported successfully." in result.output
    mock_export_api.assert_called_once_with("test-server")


@patch("bedrock_server_manager.api.world.reset_world")
@patch("click.confirm")
def test_reset_world_interactive(mock_confirm, mock_reset_api, runner, mock_bsm):
    mock_reset_api.return_value = {"status": "success"}
    result = runner.invoke(
        reset_world, ["--server", "test-server"], obj={"bsm": mock_bsm}
    )

    assert result.exit_code == 0
    assert "World has been reset successfully." in result.output
    mock_confirm.assert_called_once()
    mock_reset_api.assert_called_once_with("test-server")


@patch("bedrock_server_manager.api.world.reset_world")
def test_reset_world_yes(mock_reset_api, runner, mock_bsm):
    mock_reset_api.return_value = {"status": "success"}
    result = runner.invoke(
        reset_world, ["--server", "test-server", "--yes"], obj={"bsm": mock_bsm}
    )

    assert result.exit_code == 0
    assert "World has been reset successfully." in result.output
    mock_reset_api.assert_called_once_with("test-server")
