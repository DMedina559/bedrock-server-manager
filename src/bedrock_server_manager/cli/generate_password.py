# bedrock_server_manager/cli/generate_password.py
"""Provides a CLI utility to generate secure password hashes for Web UI authentication.

This module contains a single Click command, ``bsm generate-password``,
which interactively prompts the user for a password, confirms it, and then
outputs a bcrypt hash of that password.

The generated hash is intended to be used as the value for the
``BSM_PASSWORD`` (or equivalent, based on :const:`~.config.const.env_name`)
environment variable, which is used to secure the Bedrock Server Manager
web interface. This approach ensures that plaintext passwords are not
stored or directly used in configurations.
"""

import click

from ..config import env_name
from ..web.auth_utils import get_password_hash


@click.command("generate-password")
def generate_password_hash_command():
    """Generates a bcrypt hash for a given password, for Web UI authentication.

    This interactive command securely prompts the user to enter a new password
    and then confirm it. Upon successful confirmation, it generates a bcrypt
    hash of the password.

    The output is the generated hash, which is intended to be used as the value
    for the ``BSM_PASSWORD`` (or equivalent, based on
    :const:`~.config.const.env_name`) environment variable. This variable,
    along with ``BSM_USERNAME``, secures access to the web interface.

    The command provides clear instructions on how to use the generated hash.
    Input is hidden during password entry for security.
    """
    click.secho(
        "--- Bedrock Server Manager Password Hash Generator ---", fg="cyan", bold=True
    )
    click.secho("--- Note: Input will not be displayed ---", fg="yellow", bold=True)

    try:
        plaintext_password = click.prompt(
            "Enter a new password",
            hide_input=True,
            confirmation_prompt=True,
            prompt_suffix=": ",
        )

        if not plaintext_password:
            click.secho("Error: Password cannot be empty.", fg="red")
            raise click.Abort()

        click.echo("\nGenerating password hash using...")

        hashed_password = get_password_hash(plaintext_password)

        click.secho("Hash generated successfully.", fg="green")

        click.echo("\n" + "=" * 60)
        click.echo("=" * 60)
        click.echo("\nSet the following environment variable to secure your web UI:")
        click.echo(
            f"\n  {click.style(f'{env_name}_PASSWORD', fg='yellow')}='{hashed_password}'\n"
        )
        click.echo(
            "Note: Enclose the value in single quotes if setting it manually in a shell."
        )
        click.echo(
            f"You must also set '{click.style(f'{env_name}_USERNAME', fg='yellow')}' "
            "to your desired username."
        )
        click.echo("\n" + "=" * 60)

    except click.Abort:
        # click.prompt raises Abort on Ctrl+C, so this handles cancellation.
        click.secho("\nOperation cancelled.", fg="red")

    except Exception as e:
        click.secho(f"\nAn unexpected error occurred: {e}", fg="red")
        raise click.Abort()


if __name__ == "__main__":
    generate_password_hash_command()
