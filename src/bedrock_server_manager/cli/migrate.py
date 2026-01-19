import click


@click.group()
def migrate():
    """Migration tools."""
    pass


@migrate.command("old-config")
@click.pass_context
def migrate_old_config(ctx: click.Context):  # noqa: C901
    """Migrates settings."""
    try:
        click.echo("No migrations to complete.")
    except Exception as e:
        click.echo(f"An error occurred during migrations: {e}")
        raise click.Abort()
