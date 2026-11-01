# bedrock_server_manager/cli/logs.py
"""Define the ``bsm logs`` command for listing, selecting, viewing, and streaming logs."""

import os
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import click
import questionary

from ..context import AppContext
from ..logging import get_application_log_path


def _format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KiB"
    return f"{num_bytes / (1024 * 1024):.1f} MiB"


def _format_mtime(mtime: float) -> str:
    return datetime.fromtimestamp(mtime, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _discover_app_logs(log_dir: Path) -> Tuple[List[Path], Optional[Path]]:
    """Return ``(ordered_files_newest_first, active_file)`` for application logs."""
    if not log_dir.is_dir():
        return ([], None)
    files = [
        p
        for p in log_dir.iterdir()
        if p.is_file() and (p.suffix == ".log" or ".log." in p.name)
    ]
    files.sort(key=os.path.getmtime, reverse=True)
    active_str = get_application_log_path(str(log_dir))
    active_path = (
        Path(active_str) if active_str and os.path.isfile(active_str) else None
    )
    if active_path is None and files:
        active_path = files[0]
    return (files, active_path)


def _discover_server_logs(
    log_dir: Path, server_name: str
) -> Tuple[List[Path], Optional[Path]]:
    """Return ``(ordered_files_newest_first, active_file)`` for one server."""
    s_dir = log_dir / "servers" / server_name
    if not s_dir.is_dir():
        return ([], None)
    files = [
        p
        for p in s_dir.iterdir()
        if p.is_file() and (p.suffix == ".log" or ".log." in p.name)
    ]
    files.sort(key=os.path.getmtime, reverse=True)
    active_path = files[0] if files else None
    return (files, active_path)


def _discover_all_server_names(app_context: AppContext, log_dir: Path) -> List[str]:
    names = set(app_context.state.servers.servers.keys())
    servers_dir = app_context.settings.get("paths.servers")
    if servers_dir and os.path.isdir(str(servers_dir)):
        try:
            for entry in Path(str(servers_dir)).iterdir():
                if entry.is_dir():
                    names.add(entry.name)
        except OSError:
            pass
    servers_log_dir = log_dir / "servers"
    if servers_log_dir.is_dir():
        try:
            for entry in servers_log_dir.iterdir():
                if entry.is_dir():
                    names.add(entry.name)
        except OSError:
            pass
    return sorted(names)


def _read_tail_lines(path: Path, lines: int) -> Tuple[str, int]:
    """Return ``(tail_text, end_byte_offset)`` from ``path``."""
    with open(path, "rb") as f:
        if lines <= 0:
            data = f.read()
            return (
                data.decode("utf-8", errors="replace").replace("\r\n", "\n"),
                f.tell(),
            )
        tail: deque[bytes] = deque(maxlen=lines)
        for raw_line in f:
            tail.append(raw_line)
        end_pos = f.tell()
    return (
        b"".join(tail).decode("utf-8", errors="replace").replace("\r\n", "\n"),
        end_pos,
    )


def _follow_file(path: Path, start_pos: int, poll_interval: float = 0.25) -> None:
    """Stream appended lines from ``path`` until interrupted."""
    click.secho(
        f"\n--- Following {path.name} (Ctrl+C to stop) ---", fg="cyan", bold=True
    )
    pos = start_pos
    try:
        while True:
            if path.is_file():
                size = path.stat().st_size
                if size < pos:
                    pos = 0
                if size > pos:
                    with open(path, "rb") as f:
                        f.seek(pos)
                        chunk = f.read()
                        pos = f.tell()
                    if chunk:
                        click.echo(chunk.decode("utf-8", errors="replace"), nl=False)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        click.secho("\nStopped following log.", fg="yellow")


def _print_log_inventory(app_context: AppContext, log_dir: Path) -> None:
    app_files, app_active = _discover_app_logs(log_dir)
    click.secho("\nApplication Logs:", bold=True)
    if not app_files:
        click.echo("  (no application log files found)")
    else:
        for f in app_files:
            stat = f.stat()
            marker = " [ACTIVE]" if app_active and f == app_active else ""
            click.echo(
                f"  - {f.name} ({_format_size(stat.st_size)}, {_format_mtime(stat.st_mtime)}){marker}"
            )

    for server_name in _discover_all_server_names(app_context, log_dir):
        s_files, s_active = _discover_server_logs(log_dir, server_name)
        click.secho(f"\nServer Logs [{server_name}]:", bold=True)
        if not s_files:
            click.echo("  (no server log files found)")
        else:
            for f in s_files:
                stat = f.stat()
                marker = " [ACTIVE]" if s_active and f == s_active else ""
                click.echo(
                    f"  - {f.name} ({_format_size(stat.st_size)}, {_format_mtime(stat.st_mtime)}){marker}"
                )


@click.command("logs")
@click.option(
    "-a",
    "--app",
    "use_app",
    is_flag=True,
    help="Select the application log.",
)
@click.option(
    "-s",
    "--server",
    "server_name",
    type=str,
    help="Select logs for a specific Bedrock server.",
)
@click.option(
    "--file",
    "file_selector",
    type=str,
    help="Select a specific log file name or path.",
)
@click.option(
    "-l",
    "--list",
    "list_only",
    is_flag=True,
    help="List available application and server log files.",
)
@click.option(
    "-n",
    "--lines",
    type=click.IntRange(min=0),
    default=50,
    show_default=True,
    help="Number of trailing lines to show (0 for entire file).",
)
@click.option(
    "-f",
    "--follow",
    is_flag=True,
    help="Stream new log output continuously (like tail -f).",
)
@click.pass_context
def logs(
    ctx: click.Context,
    use_app: bool,
    server_name: Optional[str],
    file_selector: Optional[str],
    list_only: bool,
    lines: int,
    follow: bool,
):
    """List, select, view, or live-stream application and server logs."""
    app_context: AppContext = ctx.obj["app_context"]
    if not app_context.log_dir:
        raise click.ClickException("Log directory is not configured.")
    log_dir = Path(app_context.log_dir)

    if use_app and server_name:
        raise click.ClickException("Cannot specify both --app and --server.")

    if list_only:
        _print_log_inventory(app_context, log_dir)
        return

    target_path: Optional[Path] = None

    # 1. Explicit --file selector
    if file_selector:
        candidate = Path(file_selector)
        if candidate.is_file():
            target_path = candidate.resolve()
        elif server_name:
            s_candidate = log_dir / "servers" / server_name / file_selector
            if s_candidate.is_file():
                target_path = s_candidate.resolve()
        else:
            a_candidate = log_dir / file_selector
            if a_candidate.is_file():
                target_path = a_candidate.resolve()
        if target_path is None:
            raise click.ClickException(f"Log file '{file_selector}' not found.")

    # 2. Explicit --app or --server
    elif use_app:
        _, target_path = _discover_app_logs(log_dir)
        if target_path is None:
            raise click.ClickException("No application log files found.")
    elif server_name:
        _, target_path = _discover_server_logs(log_dir, server_name)
        if target_path is None:
            raise click.ClickException(
                f"No log files found for server '{server_name}'."
            )

    # 3. Interactive selection when no target flags were provided
    else:
        sources: list[questionary.Choice] = [
            questionary.Choice("Application Logs", value=("app", None))
        ]
        for s_name in _discover_all_server_names(app_context, log_dir):
            sources.append(
                questionary.Choice(f"Server: {s_name}", value=("server", s_name))
            )

        selected_source = questionary.select(
            "Select log source:", choices=sources
        ).ask()
        if not selected_source:
            return

        kind, chosen_server = selected_source
        if kind == "app":
            files, active = _discover_app_logs(log_dir)
        else:
            files, active = _discover_server_logs(log_dir, str(chosen_server))

        if not files:
            raise click.ClickException("No log files found for the selected source.")

        file_choices: list[questionary.Choice] = []
        for f in files:
            stat = f.stat()
            tag = " [ACTIVE]" if active and f == active else ""
            label = f"{f.name} ({_format_size(stat.st_size)}, {_format_mtime(stat.st_mtime)}){tag}"
            file_choices.append(questionary.Choice(label, value=f))

        target_path = questionary.select("Select log file:", choices=file_choices).ask()
        if target_path is None:
            return

        if not follow:
            action = questionary.select(
                "Select action:",
                choices=[
                    questionary.Choice(f"View last {lines} lines", value="tail"),
                    questionary.Choice("Follow / stream live (-f)", value="follow"),
                    questionary.Choice("View entire file", value="all"),
                ],
            ).ask()
            if not action:
                return
            if action == "follow":
                follow = True
            elif action == "all":
                lines = 0

    assert target_path is not None
    click.secho(f"=== {target_path} ===", fg="green", bold=True)
    try:
        text, end_pos = _read_tail_lines(target_path, lines)
    except OSError as error:
        raise click.ClickException(f"Could not read log file: {error}") from error

    if text:
        click.echo(text, nl=not text.endswith("\n"))
    else:
        click.secho("(log file is empty)", fg="yellow")

    if follow:
        _follow_file(target_path, end_pos)
