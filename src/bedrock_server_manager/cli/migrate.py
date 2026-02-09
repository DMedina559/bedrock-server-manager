import click

from ..db.models import Setting


@click.group()
def migrate():
    """Migration tools."""
    pass


@migrate.command("old-config")
@click.pass_context
def migrate_old_config(ctx: click.Context):  # noqa: C901
    """Migrates settings."""
    app_context = ctx.obj["app_context"]
    try:
        app_context.db.initialize()
        with app_context.db.session_manager() as db:
            # 1. web.threads
            web_threads = db.query(Setting).filter_by(key="web.threads").first()
            if web_threads:
                db.delete(web_threads)
                click.echo("Removed 'web.threads' setting.")

            # 2. logging.cli_level
            cli_level = db.query(Setting).filter_by(key="logging.cli_level").first()
            if cli_level:
                db.delete(cli_level)
                click.echo("Removed 'logging.cli_level' setting.")

            # 3. logging.file_level -> logging.level
            file_level = db.query(Setting).filter_by(key="logging.file_level").first()
            if file_level:
                # Check if logging.level already exists
                log_level = db.query(Setting).filter_by(key="logging.level").first()
                if not log_level:
                    # Create new logging.level with value from file_level
                    new_level = Setting(key="logging.level", value=file_level.value)
                    db.add(new_level)
                    click.echo(
                        f"Migrated 'logging.file_level' to 'logging.level' (value: {file_level.value})."
                    )
                else:
                    click.echo(
                        "'logging.level' already exists. Skipping migration from 'logging.file_level'."
                    )

                db.delete(file_level)
                click.echo("Removed 'logging.file_level' setting.")

            db.commit()
            click.echo("Migration complete.")

    except Exception as e:
        click.echo(f"An error occurred during migrations: {e}")
        raise click.Abort()
