import pytest
from click.testing import CliRunner
from unittest.mock import MagicMock, patch

from bedrock_server_manager.cli.reset_password import reset_password_command
from bedrock_server_manager.db.models import User


@pytest.fixture
def runner():
    return CliRunner()


def test_reset_password_success(runner, mocker):
    # Mock AppContext and its dependencies
    mock_user = User(username="testuser", hashed_password="old_hash")
    mock_db_session = MagicMock()
    mock_db_session.query.return_value.filter.return_value.first.return_value = (
        mock_user
    )

    mock_app_context = MagicMock()
    mock_app_context.db.session_manager.return_value.__enter__.return_value = (
        mock_db_session
    )

    mocker.patch(
        "bedrock_server_manager.cli.reset_password.get_password_hash",
        return_value="new_hash",
    )

    result = runner.invoke(
        reset_password_command,
        ["testuser"],
        input="new_password\nnew_password\n",
        obj={"app_context": mock_app_context},
    )

    assert result.exit_code == 0
    assert "Password for user 'testuser' has been reset successfully." in result.output
    assert mock_user.hashed_password == "new_hash"
    mock_db_session.commit.assert_called_once()


def test_reset_password_user_not_found(runner, mocker):
    # Mock AppContext and its dependencies
    mock_db_session = MagicMock()
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    mock_app_context = MagicMock()
    mock_app_context.db.session_manager.return_value.__enter__.return_value = (
        mock_db_session
    )

    result = runner.invoke(
        reset_password_command,
        ["nonexistentuser"],
        input="new_password\nnew_password\n",
        obj={"app_context": mock_app_context},
    )

    assert result.exit_code == 0
    assert "Error: User 'nonexistentuser' not found." in result.output
