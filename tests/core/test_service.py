import platform
import sys

import pytest

from bedrock_server_manager.core import service


@pytest.fixture
def mock_linux(mocker):
    mocker.patch("platform.system", return_value="Linux")
    mocker.patch(
        "bedrock_server_manager.core.service.WEB_SERVICE_SYSTEMD_NAME",
        "bedrock-server-manager-webui.service",
    )


@pytest.fixture
def mock_windows(mocker):
    mocker.patch("platform.system", return_value="Windows")
    mocker.patch(
        "bedrock_server_manager.core.service.WEB_SERVICE_WINDOWS_NAME_INTERNAL",
        "BedrockServerManagerWebUI",
    )
    mocker.patch(
        "bedrock_server_manager.core.service.WEB_SERVICE_WINDOWS_DISPLAY_NAME",
        "Bedrock Server Manager Web UI",
    )
    mocker.patch(
        "shutil.which",
        lambda cmd: r"C:\Windows\System32\sc.exe" if cmd == "sc.exe" else None,
    )


def test_build_web_service_start_command(mocker):
    mocker.patch("sys.executable", "/fake/python")
    command = service._build_web_service_start_command()
    assert command == "/fake/python -m bedrock_server_manager web start --mode direct"


def test_build_web_service_start_command_with_spaces(mocker):
    mocker.patch("sys.executable", "/fake path/python")
    command = service._build_web_service_start_command()
    assert (
        command
        == '"/fake path/python" -m bedrock_server_manager web start --mode direct'
    )


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux specific service tests")
def test_create_web_service_file_linux(mock_linux, mocker):
    mock_create_systemd = mocker.patch(
        "bedrock_server_manager.core.system.linux.create_systemd_service_file"
    )
    mocker.patch("os.path.isdir", return_value=True)

    service.create_web_service_file("/fake/app_data")

    exe_path = sys.executable
    if " " in exe_path and not exe_path.startswith('"') and not exe_path.endswith('"'):
        exe_path = f'"{exe_path}"'

    mock_create_systemd.assert_called_once_with(
        service_name_full="bedrock-server-manager-webui.service",
        description=mocker.ANY,
        system=False,
        working_directory="/fake/app_data",
        exec_start_command=f"{exe_path} -m bedrock_server_manager web start --mode direct",
        exec_stop_command=f"{exe_path} -m bedrock_server_manager web stop",
        service_type="simple",
        restart_policy="on-failure",
        restart_sec=10,
        after_targets="network.target",
    )


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux specific service tests")
def test_check_web_service_exists_linux(mock_linux, mocker):
    mock_check_exists = mocker.patch(
        "bedrock_server_manager.core.system.linux.check_service_exists",
        return_value=True,
    )
    assert service.check_web_service_exists() is True
    mock_check_exists.assert_called_once_with(
        "bedrock-server-manager-webui.service", system=False
    )


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux specific service tests")
def test_enable_web_service_linux(mock_linux, mocker):
    mock_enable_systemd = mocker.patch(
        "bedrock_server_manager.core.system.linux.enable_systemd_service"
    )
    service.enable_web_service()
    mock_enable_systemd.assert_called_once_with(
        "bedrock-server-manager-webui.service", system=False
    )


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux specific service tests")
def test_disable_web_service_linux(mock_linux, mocker):
    mock_disable_systemd = mocker.patch(
        "bedrock_server_manager.core.system.linux.disable_systemd_service"
    )
    service.disable_web_service()
    mock_disable_systemd.assert_called_once_with(
        "bedrock-server-manager-webui.service", system=False
    )


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux specific service tests")
def test_remove_web_service_file_linux_exists(mock_linux, mocker):
    mocker.patch(
        "bedrock_server_manager.core.system.linux.get_systemd_service_file_path",
        return_value="/fake/service.file",
    )
    mocker.patch("os.path.isfile", return_value=True)
    mock_os_remove = mocker.patch("os.remove")
    mocker.patch("shutil.which", return_value="/usr/bin/systemctl")
    mock_subprocess_run = mocker.patch("subprocess.run")

    assert service.remove_web_service_file() is True
    mock_os_remove.assert_called_once_with("/fake/service.file")
    mock_subprocess_run.assert_called_once_with(
        ["/usr/bin/systemctl", "--user", "daemon-reload"],
        check=False,
        capture_output=True,
    )


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux specific service tests")
def test_is_web_service_active_linux(mock_linux, mocker, fp):
    mocker.patch("shutil.which", return_value="/usr/bin/systemctl")
    expected_command = [
        "/usr/bin/systemctl",
        "--user",
        "is-active",
        "bedrock-server-manager-webui.service",
    ]

    fp.register(expected_command, returncode=0, stdout="active")
    assert service.is_web_service_active() is True
    assert fp.call_count(expected_command) == 1


@pytest.mark.skipif(
    platform.system() != "Windows", reason="Windows specific service tests"
)
def test_create_web_service_file_windows(mock_windows, mocker):
    mock_create_svc = mocker.patch(
        "bedrock_server_manager.core.system.windows.create_windows_service"
    )

    service.create_web_service_file("/fake/app_data")

    exe_path = sys.executable
    if " " in exe_path and not exe_path.startswith('"') and not exe_path.endswith('"'):
        exe_path = f'"{exe_path}"'

    expected_binpath_command = f'{exe_path} -m bedrock_server_manager service _run-web "BedrockServerManagerWebUI"'
    mock_create_svc.assert_called_once_with(
        service_name="BedrockServerManagerWebUI",
        display_name="Bedrock Server Manager Web UI",
        description=mocker.ANY,
        command=expected_binpath_command,
        username=None,
        password=None,
    )


@pytest.mark.skipif(
    platform.system() != "Windows", reason="Windows specific service tests"
)
def test_check_web_service_exists_windows(mock_windows, mocker):
    mock_check_exists = mocker.patch(
        "bedrock_server_manager.core.system.windows.check_service_exists",
        return_value=True,
    )
    assert service.check_web_service_exists() is True
    mock_check_exists.assert_called_once_with("BedrockServerManagerWebUI")
