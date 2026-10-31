import pytest
from click.testing import CliRunner
from sqlalchemy import select

from bedrock_server_manager.cli.reset_password import reset_password_command
from bedrock_server_manager.db.models import User
from bedrock_server_manager.web.auth import get_password_hash, verify_password


@pytest.fixture
def runner():
    return CliRunner()


async def test_reset_password_success(runner, app_context, db_session):
    """Test the reset-password CLI command successfully changes an existing user's password."""
    # Setup user
    old_hash = get_password_hash("old_pw")
    user = User(username="target_user", hashed_password=old_hash, role="admin")
    db_session.add(user)
    await db_session.commit()

    # Run CLI command passing input twice for password and confirmation
    result = runner.invoke(
        reset_password_command,
        ["target_user"],
        input="new secure passphrase\nnew secure passphrase\n",
        obj={"app_context": app_context},
    )

    assert result.exit_code == 0
    assert (
        "Password for user 'target_user' has been reset successfully." in result.output
    )

    # Verify hash was updated
    db_session.expire_all()
    res = await db_session.execute(select(User).filter(User.username == "target_user"))
    updated_user = res.scalars().first()
    assert verify_password("new secure passphrase", updated_user.hashed_password)


async def test_reset_password_user_not_found(runner, app_context):
    """Test the reset-password CLI command cleanly fails when a user is not found."""
    result = runner.invoke(
        reset_password_command,
        ["non_existent_user"],
        input="new secure passphrase\nnew secure passphrase\n",
        obj={"app_context": app_context},
    )

    assert result.exit_code == 0
    assert "Error: User 'non_existent_user' not found." in result.output


async def test_reset_password_mismatch_confirmation(runner, app_context):
    """Test the reset-password CLI command fails and aborts on prompt confirmation mismatch."""
    # Setup user
    old_hash = get_password_hash("old_pw")
    async with app_context.db.session_manager() as db_session:
        user = User(username="target_user", hashed_password=old_hash, role="admin")
        db_session.add(user)
        await db_session.commit()

    result = runner.invoke(
        reset_password_command,
        ["target_user"],
        input="new secure passphrase\nwrong_pw\n",
        obj={"app_context": app_context},
    )

    # click prompt will fail and abort with an error on mismatch
    assert result.exit_code == 1  # aborted
    assert "Error: The two entered values do not match" in result.output


async def test_local_mfa_reset_revokes_logins_without_changing_password(
    runner, app_context, auth_client
):
    from bedrock_server_manager.cli.reset_password import reset_mfa_command
    from bedrock_server_manager.db.models import AccountSecurity, LoginSession

    async with app_context.storage.transaction() as session:
        user = await session.scalar(select(User).where(User.username == "testuser"))
        original_hash = user.hashed_password
        session.add(
            AccountSecurity(
                owner_id=user.access_id,
                totp_secret="encrypted-factor",
                recovery_hashes=[],
                last_counter=-1,
                version=0,
            )
        )
    result = runner.invoke(
        reset_mfa_command, ["testuser", "--yes"], obj={"app_context": app_context}
    )
    assert result.exit_code == 0, result.output
    assert "All login sessions were signed out" in result.output
    async with app_context.storage.transaction() as session:
        user = await session.scalar(select(User).where(User.username == "testuser"))
        assert user.hashed_password == original_hash
        assert (await session.get(AccountSecurity, user.access_id)).totp_secret is None
        assert all(
            row.revoked_at is not None
            for row in (
                await session.scalars(
                    select(LoginSession).where(LoginSession.owner_id == user.access_id)
                )
            ).all()
        )


async def test_local_mfa_reset_requires_confirmation(runner, app_context):
    from bedrock_server_manager.cli.reset_password import reset_mfa_command

    result = runner.invoke(
        reset_mfa_command, ["testuser"], input="n\n", obj={"app_context": app_context}
    )
    assert result.exit_code != 0
