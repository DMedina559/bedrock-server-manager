import click
from sqlalchemy import select

from ..db.models import User
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
        async with app_context.db.session_manager() as db:
            result = await db.execute(select(User).filter(User.username == username))
            user = result.scalars().first()
            if not user:
                click.secho(f"Error: User '{username}' not found.", fg="red")
                return

            user.hashed_password = get_password_hash(password)
            await db.commit()
            click.secho(
                f"Password for user '{username}' has been reset successfully.",
                fg="green",
            )

    run_async(_reset())
