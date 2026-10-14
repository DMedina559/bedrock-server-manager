import subprocess
from types import SimpleNamespace

import pytest

from bedrock_server_manager.config.const import WEB_SERVICE_SYSTEMD_NAME
from bedrock_server_manager.core import service as service_core
from bedrock_server_manager.core.system import linux


@pytest.fixture
def systemd(app_context, tmp_path, monkeypatch):
    state = SimpleNamespace(enabled=False, active=False, commands=[], failure=None)
    which = service_core.shutil.which

    def service_path(name, system=False):
        return str(tmp_path / ("system" if system else "user") / name)

    def run(command, **kwargs):
        assert command[0] == "/test/bin/systemctl"
        assert all(command)
        state.commands.append(command)
        action = command[2] if command[1] == "--user" else command[1]
        if state.failure == action:
            raise subprocess.CalledProcessError(
                1, command, stderr="Injected systemctl failure"
            )
        stdout, code = "", 0
        if action == "enable":
            state.enabled = True
        elif action == "disable":
            state.enabled = False
        elif action == "is-enabled":
            stdout, code = ("enabled", 0) if state.enabled else ("disabled", 1)
        elif action == "is-active":
            stdout, code = ("active", 0) if state.active else ("inactive", 3)
        else:
            assert action == "daemon-reload"
        return subprocess.CompletedProcess(command, code, stdout=stdout, stderr="")

    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr(service_core, "system_linux_utils", linux, raising=False)
    monkeypatch.setattr(
        service_core.shutil,
        "which",
        lambda cmd: "/test/bin/systemctl" if cmd == "systemctl" else which(cmd),
    )
    monkeypatch.setattr(linux, "get_systemd_service_file_path", service_path)
    monkeypatch.setattr(linux.os, "getlogin", lambda: "testuser")
    monkeypatch.setattr(service_core.subprocess, "run", run)
    state.path = (
        lambda system=False: tmp_path
        / ("system" if system else "user")
        / WEB_SERVICE_SYSTEMD_NAME
    )
    return state
