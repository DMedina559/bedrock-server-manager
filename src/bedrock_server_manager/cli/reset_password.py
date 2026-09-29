import click

from ..utils import get_password_hash
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
        async with app_context.storage.transaction() as session:
            hashed_pwd = get_password_hash(password)
            success = await app_context.storage.user_repo.update_password(
                session, username, hashed_pwd
            )
            if not success:
                click.secho(f"Error: User '{username}' not found.", fg="red")
                return

            click.secho(
                f"Password for user '{username}' has been reset successfully.",
                fg="green",
            )

    run_async(_reset())
