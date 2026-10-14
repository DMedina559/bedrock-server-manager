"""Shared file checks for server references; no process sampling."""

import os
import platform
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state.app_state import AppState


def valid_server_names(state: "AppState") -> list[str]:
    base = state.settings.paths.servers
    executable = (
        "bedrock_server.exe" if platform.system() == "Windows" else "bedrock_server"
    )
    return sorted(
        name
        for name in state.servers.servers
        if re.fullmatch(r"[a-zA-Z0-9_-]+", name)
        and os.path.isfile(os.path.join(base, name, executable))
        and os.path.isfile(os.path.join(base, name, "server.properties"))
    )
