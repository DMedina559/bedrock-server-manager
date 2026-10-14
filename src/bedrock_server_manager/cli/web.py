"""Web hosting commands call the runtime directly, outside AppAPI."""

import asyncio

import click

from ..error import BSMError
from ..web.process import WebProcessPaths, start_detached, stop_local
from ..web.runtime import WebRunOptions


def run_web_server(*args, **kwargs):
    from ..web.main import run_web_server as run

    return run(*args, **kwargs)


@click.group()
def web():
    """Manage the local web runtime."""


def _paths(context) -> WebProcessPaths:
    return WebProcessPaths(
        config_dir=context.config_dir, data_dir=context.data_dir, db_url=context.db_url
    )


@web.command("start")
@click.option("-H", "--host", type=str, help="Host address to bind to.")
@click.option(
    "-p", "--port", type=click.IntRange(1, 65535), help="Override the configured port."
)
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    help="Enable Uvicorn debug logging; no reload supervisor.",
)
@click.option(
    "-m",
    "--mode",
    type=click.Choice(["direct", "detached"]),
    default="direct",
    show_default=True,
)
@click.option("--instance-id", hidden=True)
@click.pass_context
def start_web_server(ctx, host, port, debug, mode, instance_id):
    """Start directly or detach and wait for HTTP readiness."""
    context = ctx.obj["app_context"]
    options = WebRunOptions(host=host, port=port, debug=debug, instance_id=instance_id)
    click.echo(f"Attempting to start web server in '{mode}' mode...")
    try:
        if mode == "direct":
            click.secho(
                "Server will run in this terminal. Press Ctrl+C to stop.", fg="cyan"
            )
            run_web_server(context, **options.model_dump())
        else:
            pid = asyncio.run(start_detached(_paths(context), options))
            click.echo(f"Web server started (PID: {pid}).")
    except (BSMError, RuntimeError, TimeoutError) as error:
        raise click.ClickException(f"Failed to start web server: {error}") from error


@web.command("stop")
@click.option(
    "--force",
    is_flag=True,
    help="Allow verified process termination if graceful shutdown fails.",
)
@click.option(
    "--timeout", type=click.FloatRange(min=1, max=3600), default=180, show_default=True
)
@click.pass_context
def stop_web_server(ctx, force, timeout):
    """Request graceful shutdown of the local runtime and await cleanup."""
    try:
        message = asyncio.run(
            stop_local(_paths(ctx.obj["app_context"]), timeout=timeout, force=force)
        )
        click.echo(message)
    except BSMError as error:
        raise click.ClickException(f"Failed to stop web server: {error}") from error
