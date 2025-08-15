import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from bedrock_server_manager.cli.main_menus import (
    main_menu,
    manage_server_menu,
    _world_management_menu,
    _backup_restore_menu,
    _handle_plugin_custom_menus,
)
from bedrock_server_manager.error import UserExitError


@pytest.fixture
def mock_bsm():
    """Fixture for a mocked BedrockServerManager."""
    bsm = MagicMock()
    bsm.get_servers_data.return_value = ([], [])
    return bsm


@pytest.fixture
def mock_ctx(mock_bsm):
    """Fixture for a mocked click context."""
    ctx = MagicMock()
    ctx.obj = {
        "bsm": mock_bsm,
        "cli": MagicMock(),
        "plugin_manager": MagicMock(),
    }
    return ctx


def test_main_menu_exit(mock_ctx):
    """Test that the main menu exits cleanly."""
    with patch("questionary.select") as mock_select:
        mock_select.return_value.ask.return_value = "Exit"
        with pytest.raises(UserExitError):
            main_menu(mock_ctx)


def test_main_menu_cancel(mock_ctx):
    """Test that the main menu handles cancellation."""
    with patch("questionary.select") as mock_select:
        mock_select.return_value.ask.return_value = None
        with pytest.raises(UserExitError):
            main_menu(mock_ctx)


def test_main_menu_install_server(mock_ctx):
    """Test the main menu's 'Install New Server' option."""
    with (
        patch("questionary.select") as mock_select,
        patch("questionary.press_any_key_to_continue") as mock_pause,
    ):
        mock_select.return_value.ask.side_effect = ["Install New Server", "Exit"]
        mock_pause.return_value.ask.return_value = None

        server_group = MagicMock()
        install_cmd = MagicMock()
        server_group.get_command.return_value = install_cmd
        mock_ctx.obj["cli"].get_command.return_value = server_group

        with pytest.raises(UserExitError):
            main_menu(mock_ctx)

        mock_ctx.invoke.assert_any_call(install_cmd)


def test_main_menu_manage_server(mock_ctx):
    """Test the main menu's 'Manage Existing Server' option."""
    mock_bsm = mock_ctx.obj["bsm"]
    mock_bsm.get_servers_data.return_value = (
        [{"name": "test-server"}],
        ["test-server"],
    )

    with (
        patch("questionary.select") as mock_select,
        patch(
            "bedrock_server_manager.cli.main_menus.get_server_name_interactively"
        ) as mock_get_server,
        patch(
            "bedrock_server_manager.cli.main_menus.manage_server_menu"
        ) as mock_manage_menu,
    ):
        mock_select.return_value.ask.side_effect = ["Manage Existing Server", "Exit"]
        mock_get_server.return_value = "test-server"

        with pytest.raises(UserExitError):
            main_menu(mock_ctx)

        mock_get_server.assert_called_once()
        mock_manage_menu.assert_called_once_with(mock_ctx, "test-server")


def test_manage_server_menu_back(mock_ctx):
    """Test that the manage server menu can exit back to the main menu."""
    with patch("questionary.select") as mock_select:
        mock_select.return_value.ask.return_value = "Back to Main Menu"
        manage_server_menu(mock_ctx, "test-server")
        # Assert that no command other than list_servers was invoked
        for call in mock_ctx.invoke.call_args_list:
            assert call.args[0].name == "list-servers"


def test_manage_server_menu_start_server(mock_ctx):
    """Test the 'Start Server' option in the manage server menu."""
    with patch("questionary.select") as mock_select, patch("click.pause") as mock_pause:
        mock_select.return_value.ask.side_effect = ["Start Server", "Back to Main Menu"]

        server_group = MagicMock()
        start_cmd = MagicMock()
        start_cmd.name = "start"
        server_group.get_command.return_value = start_cmd
        mock_ctx.obj["cli"].get_command.return_value = server_group

        manage_server_menu(mock_ctx, "test-server")

        mock_ctx.invoke.assert_any_call(start_cmd, server_name="test-server")


def test_manage_server_menu_send_command_no_input(mock_ctx):
    """Test the 'Send Command to Server' option with no input."""
    with (
        patch("questionary.select") as mock_select,
        patch("questionary.text") as mock_text,
        patch("click.pause"),
    ):
        mock_select.return_value.ask.side_effect = [
            "Send Command to Server",
            "Back to Main Menu",
        ]
        mock_text.return_value.ask.return_value = ""

        server_group = MagicMock()
        send_cmd = MagicMock()
        send_cmd.name = "send-command"
        server_group.get_command.return_value = send_cmd
        mock_ctx.obj["cli"].get_command.return_value = server_group

        manage_server_menu(mock_ctx, "test-server")

        # The send_cmd should not be invoked if the input is empty
        for call in mock_ctx.invoke.call_args_list:
            assert call.args[0].name != "send-command"


def test_world_management_menu(mock_ctx):
    """Test the world management sub-menu."""
    with patch("questionary.select") as mock_select:
        mock_select.return_value.ask.side_effect = ["Install/Replace World", "Back"]

        world_group = MagicMock()
        install_cmd = MagicMock()
        world_group.get_command.return_value = install_cmd
        mock_ctx.obj["cli"].get_command.return_value = world_group

        _world_management_menu(mock_ctx, "test-server")

        mock_ctx.invoke.assert_called_once_with(install_cmd, server_name="test-server")


def test_world_management_menu_command_not_found(mock_ctx):
    """Test the world management sub-menu when a command is not found."""
    with patch("questionary.select") as mock_select, patch("click.secho") as mock_secho:
        mock_select.return_value.ask.side_effect = ["Install/Replace World", "Back"]

        world_group = MagicMock()
        world_group.get_command.return_value = None
        mock_ctx.obj["cli"].get_command.return_value = world_group

        _world_management_menu(mock_ctx, "test-server")

        mock_ctx.invoke.assert_not_called()


def test_backup_restore_menu(mock_ctx):
    """Test the backup/restore sub-menu."""
    with patch("questionary.select") as mock_select:
        mock_select.return_value.ask.side_effect = ["Create Backup", "Back"]

        backup_group = MagicMock()
        create_cmd = MagicMock()
        backup_group.get_command.return_value = create_cmd
        mock_ctx.obj["cli"].get_command.return_value = backup_group

        _backup_restore_menu(mock_ctx, "test-server")

        mock_ctx.invoke.assert_called_once_with(create_cmd, server_name="test-server")


def test_handle_plugin_custom_menus(mock_ctx):
    """Test the handler for plugin custom menus."""
    mock_handler = MagicMock()
    plugin_menu_items = [
        {
            "name": "Test Plugin Menu",
            "handler": mock_handler,
            "plugin_name": "test-plugin",
        }
    ]

    with (
        patch("questionary.select") as mock_select,
        patch("questionary.press_any_key_to_continue") as mock_pause,
    ):
        mock_select.return_value.ask.return_value = (
            "Test Plugin Menu (plugin: test-plugin)"
        )
        mock_pause.return_value.ask.return_value = None

        _handle_plugin_custom_menus(mock_ctx, plugin_menu_items)

        mock_handler.assert_called_once_with(mock_ctx)
