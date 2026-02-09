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
            # First, try deleting legacy full key if exists
            web_threads_deleted = (
                db.query(Setting).filter_by(key="web.threads").delete()
            )
            if web_threads_deleted > 0:
                click.echo(f"Removed {web_threads_deleted} 'web.threads' setting(s).")

            # Check inside 'web' key JSON
            web_setting = db.query(Setting).filter_by(key="web").first()
            if web_setting and isinstance(web_setting.value, dict):
                current_value = web_setting.value
                if "threads" in current_value:
                    # Create a completely new dictionary
                    new_value = dict(current_value)
                    del new_value["threads"]

                    # Update the value
                    web_setting.value = new_value

                    # Mark as dirty - SQLAlchemy needs this for JSON
                    from sqlalchemy.orm.attributes import flag_modified

                    flag_modified(web_setting, "value")

                    db.add(web_setting)
                    click.echo("Removed 'threads' from 'web' setting.")
                else:
                    click.echo("'threads' not found in 'web' setting.")
            else:
                click.echo("'web' setting not found or is not a dict.")

            # 2. logging.cli_level
            # First, try deleting legacy full key
            cli_level_deleted = (
                db.query(Setting).filter_by(key="logging.cli_level").delete()
            )
            if cli_level_deleted > 0:
                click.echo(
                    f"Removed {cli_level_deleted} 'logging.cli_level' setting(s)."
                )

            # Check inside 'logging' key JSON
            logging_setting = db.query(Setting).filter_by(key="logging").first()
            if logging_setting and isinstance(logging_setting.value, dict):
                new_value = logging_setting.value.copy()
                modified = False

                # 2. Remove cli_level
                if "cli_level" in new_value:
                    del new_value["cli_level"]
                    modified = True
                    click.echo("Removed 'cli_level' from 'logging' setting.")
                else:
                    click.echo("'cli_level' not found in 'logging' setting.")

                # 3. Migrate file_level -> level
                if "file_level" in new_value:
                    file_level_val = new_value["file_level"]
                    if "level" not in new_value:
                        new_value["level"] = file_level_val
                        click.echo(
                            f"Migrated 'file_level' to 'level' in 'logging' setting (value: {file_level_val})."
                        )
                    else:
                        click.echo(
                            "'level' already exists in 'logging' setting. Skipping migration from 'file_level'."
                        )
                    del new_value["file_level"]
                    modified = True
                    click.echo("Removed 'file_level' from 'logging' setting.")
                else:
                    click.echo("'file_level' not found in 'logging' setting.")

                if modified:
                    logging_setting.value = new_value
                    db.add(logging_setting)

            else:
                click.echo("'logging' setting not found or is not a dict.")

            # 3. Clean up legacy 'logging.file_level' row if it exists
            # (Just in case mixed data exists)
            file_level = db.query(Setting).filter_by(key="logging.file_level").first()
            if file_level:
                # Check if logging.level already exists (as a standalone key)
                log_level = db.query(Setting).filter_by(key="logging.level").first()
                if not log_level:
                    # Also check if it exists inside 'logging' JSON (we just handled that above, but purely for standalone case)
                    # If we just migrated it inside the JSON, we might not want to create a separate key.
                    # But if the user has a mix of flat keys and JSON keys, it's messy.
                    # Let's assume we prioritize JSON structure if 'logging' exists.

                    # If 'logging' parent key didn't exist or didn't have 'level', we could migrate here.
                    # But for simplicity, let's just create the new key if it's missing globally.
                    # Check the 'logging' parent again
                    logging_setting_ref = (
                        db.query(Setting).filter_by(key="logging").first()
                    )
                    has_level_in_json = (
                        logging_setting_ref
                        and isinstance(logging_setting_ref.value, dict)
                        and "level" in logging_setting_ref.value
                    )

                    if not has_level_in_json:
                        # Create new logging.level with value from file_level
                        # But wait, should we put it in 'logging' JSON or 'logging.level' row?
                        # The code seems to use `settings.get("logging.level")` which traverses JSON.
                        # So putting it in 'logging' JSON is preferred if 'logging' exists.
                        if logging_setting_ref and isinstance(
                            logging_setting_ref.value, dict
                        ):
                            new_val = logging_setting_ref.value.copy()
                            new_val["level"] = file_level.value
                            logging_setting_ref.value = new_val
                            click.echo(
                                f"Migrated standalone 'logging.file_level' to 'level' inside 'logging' setting."
                            )
                        else:
                            # Create standalone 'logging.level' if 'logging' parent doesn't exist
                            new_level = Setting(
                                key="logging.level", value=file_level.value
                            )
                            db.add(new_level)
                            click.echo(
                                f"Migrated standalone 'logging.file_level' to standalone 'logging.level'."
                            )
                else:
                    click.echo(
                        "'logging.level' already exists. Skipping migration from standalone 'logging.file_level'."
                    )

                file_level_deleted = (
                    db.query(Setting).filter_by(key="logging.file_level").delete()
                )
                click.echo(
                    f"Removed {file_level_deleted} standalone 'logging.file_level' setting(s)."
                )

            db.commit()
            click.echo("Migration complete.")

    except Exception as e:
        click.echo(f"An error occurred during migrations: {e}")
        raise click.Abort()
