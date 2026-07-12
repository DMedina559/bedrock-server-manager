import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.reset_password import reset_password_command
from bedrock_server_manager.db.models import User
from bedrock_server_manager.utils.auth import get_password_hash, verify_password


@pytest.fixture
def runner():
    return CliRunner()


def test_reset_password_success(runner, app_context, db_session):
    """Test the reset-password CLI command successfully changes an existing user's password."""
    # Setup user
    old_hash = get_password_hash("old_pw")
    user = User(username="target_user", hashed_password=old_hash, role="admin")
    db_session.add(user)
    db_session.commit()

    # Run CLI command passing input twice for password and confirmation
    result = runner.invoke(
        reset_password_command,
        ["target_user"],
        input="new_pw\nnew_pw\n",
        obj={"app_context": app_context},
    )

    assert result.exit_code == 0
    assert (
        "Password for user 'target_user' has been reset successfully." in result.output
    )

    # Verify hash was updated
    updated_user = db_session.query(User).filter(User.username == "target_user").first()
    assert verify_password("new_pw", updated_user.hashed_password)


def test_reset_password_user_not_found(runner, app_context):
    """Test the reset-password CLI command cleanly fails when a user is not found."""
    result = runner.invoke(
        reset_password_command,
        ["non_existent_user"],
        input="new_pw\nnew_pw\n",
        obj={"app_context": app_context},
    )

    assert result.exit_code == 0
    assert "Error: User 'non_existent_user' not found." in result.output


def test_reset_password_mismatch_confirmation(runner, app_context):
    """Test the reset-password CLI command fails and aborts on prompt confirmation mismatch."""
    # Setup user
    old_hash = get_password_hash("old_pw")
    with app_context.db.session_manager() as db_session:
        user = User(username="target_user", hashed_password=old_hash, role="admin")
        db_session.add(user)
        db_session.commit()

    result = runner.invoke(
        reset_password_command,
        ["target_user"],
        input="new_pw\nwrong_pw\n",
        obj={"app_context": app_context},
    )

    # click prompt will fail and abort with an error on mismatch
    assert result.exit_code == 1  # aborted
    assert "Error: The two entered values do not match" in result.output
