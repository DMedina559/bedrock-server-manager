import click

from ..context import AppContext
from ..db.models import User
from ..web.auth_utils import get_password_hash


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

    with app_context.db.session_manager() as db:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            click.secho(f"Error: User '{username}' not found.", fg="red")
            return

        user.hashed_password = get_password_hash(password)
        db.commit()
        click.secho(
            f"Password for user '{username}' has been reset successfully.", fg="green"
        )
