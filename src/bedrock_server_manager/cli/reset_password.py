import click

from ..utils.general import run_async


@click.command("reset-password", help="Resets the password for a user.")
@click.argument("username")
@click.pass_context
def reset_password_command(ctx, username: str):
    """
    Resets the password for a given user.
    """
    app_context = ctx.obj["app_context"]
    password = click.prompt(
        "Enter new password", hide_input=True, confirmation_prompt=True
    )

    async def _reset():
        success = await app_context.user_service.reset_password(username, password)
        if not success:
            click.secho(f"Error: User '{username}' not found.", fg="red")
            return

        click.secho(
            f"Password for user '{username}' has been reset successfully.",
            fg="green",
        )

    try:
        run_async(_reset())
    except Exception as error:
        from ..error import UserInputError

        if isinstance(error, UserInputError):
            raise click.ClickException(str(error)) from None
        raise


@click.command(
    "reset-mfa",
    help="Locally reset an account's MFA and revoke all its login sessions.",
)
@click.argument("username")
@click.confirmation_option(prompt="Reset MFA and sign out all logins for this account?")
@click.pass_context
def reset_mfa_command(ctx, username: str):
    """Recovery requires access to the manager's local configuration/database."""
    app_context = ctx.obj["app_context"]

    async def reset():
        async with app_context.storage.transaction() as session:
            user = await app_context.storage.user_repo.get_user_by_username(
                session, username
            )
            if user is None:
                raise click.ClickException("Account not found.")
            identifier, user_id = user.access_id, user.id
        await app_context.session_service.change_factor(identifier, disable=True)
        await app_context.session_service.event(user_id, "local_mfa_reset")
        click.echo(
            "MFA reset. All login sessions were signed out; integration credentials are unchanged."
        )

    run_async(reset())
