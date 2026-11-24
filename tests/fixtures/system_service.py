import subprocess
from types import SimpleNamespace

import pytest

import bedrock_server_manager.cli.service as service_cli
from bedrock_server_manager.config.const import WEB_SERVICE_SYSTEMD_NAME
from bedrock_server_manager.core import service as service_core
from bedrock_server_manager.core.system import linux


@pytest.fixture
def systemd(app_context, tmp_path, monkeypatch):
    state = SimpleNamespace(
        available=True, enabled=False, active=False, commands=[], failure=None
    )
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

    platform = SimpleNamespace(system=lambda: "Linux")
    for module in (service_core, service_cli, linux):
        monkeypatch.setattr(module, "platform", platform)
    monkeypatch.setattr(service_cli, "can_manage_services", lambda: state.available)
    monkeypatch.setattr(service_core, "system_linux_utils", linux, raising=False)
    system_tools = SimpleNamespace(
        which=lambda command: (
            "/test/bin/systemctl" if command == "systemctl" else which(command)
        )
    )
    monkeypatch.setattr(service_core, "shutil", system_tools)
    monkeypatch.setattr(linux, "shutil", system_tools)
    monkeypatch.setattr(linux, "get_systemd_service_file_path", service_path)
    monkeypatch.setattr(
        linux,
        "os",
        SimpleNamespace(
            getlogin=lambda: "testuser", path=linux.os.path, makedirs=linux.os.makedirs
        ),
    )
    monkeypatch.setattr(service_core, "_run_service_command", run)
    monkeypatch.setattr(linux, "_run_service_command", run)
    state.path = (
        lambda system=False: tmp_path
        / ("system" if system else "user")
        / WEB_SERVICE_SYSTEMD_NAME
    )
    return state
