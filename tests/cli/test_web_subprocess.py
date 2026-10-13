import asyncio
import json
import os
import signal
import socket
import sys
import tempfile
from pathlib import Path

import psutil
import pytest
from httpx2 import AsyncClient, TransportError


@pytest.fixture
def web_process_config(tmp_path):
    config = tmp_path / "config"
    data = tmp_path / "data"
    config.mkdir()
    data.mkdir()
    (config / "bedrock_server_manager.json").write_text(
        json.dumps(
            {"data_dir": str(data), "db_url": f"sqlite:///{data / 'manager.db'}"}
        )
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    command = [
        sys.executable,
        "-m",
        "bedrock_server_manager",
        "--config-dir",
        str(config),
        "--data-dir",
        str(data),
    ]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        str(Path(entry).resolve())
        for entry in environment.get("PYTHONPATH", "").split(os.pathsep)
        if entry
    )
    environment["PYTHONUNBUFFERED"] = "1"
    return config, command, environment, port


async def wait_for_http(port, process=None):
    async with AsyncClient(timeout=1, trust_env=False) as client:
        async with asyncio.timeout(20):
            while True:
                if process is not None and process.returncode is not None:
                    raise AssertionError(
                        f"Web process exited before serving HTTP: {process.returncode}"
                    )
                try:
                    response = await client.get(f"http://127.0.0.1:{port}/api/info")
                    if response.status_code == 200:
                        assert response.headers["content-type"].startswith(
                            "application/json"
                        )
                        assert response.json()["info"]["app_version"]
                        return
                except TransportError:
                    pass
                await asyncio.sleep(0.05)


async def run_cli(command, environment, *arguments):
    # A real file avoids proactor pipe transports surviving a failed CLI run.
    with tempfile.TemporaryFile() as output_file:
        process = await asyncio.create_subprocess_exec(
            *command,
            *arguments,
            env=environment,
            stdout=output_file,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            await asyncio.wait_for(process.wait(), 20)
            output_file.seek(0)
            output = output_file.read().decode(errors="replace")
            assert process.returncode == 0, output
            return output
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()


@pytest.mark.skipif(os.name == "nt", reason="Foreground interruption uses POSIX SIGINT")
async def test_direct_web_cli_serves_http_and_shuts_down(web_process_config, tmp_path):
    config, command, environment, port = web_process_config
    log = tmp_path / "web-process.log"
    with log.open("wb") as output:
        process = await asyncio.create_subprocess_exec(
            *command,
            "web",
            "start",
            "--mode",
            "direct",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            env=environment,
            stdout=output,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            await wait_for_http(port, process)
            process.send_signal(signal.SIGINT)
            await asyncio.wait_for(process.wait(), 20)
            assert process.returncode == 1, log.read_text(errors="replace")
            # Click reports an interrupted foreground command with exit code 1.
            assert "Application shutdown complete" in log.read_text()
            assert not (config / "web_server.pid").exists()
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()


async def test_detached_web_cli_serves_requested_port_and_cleans_pid(
    web_process_config,
):
    config, command, environment, port = web_process_config
    pid_file = config / "web_server.pid"
    pid = None
    try:
        await run_cli(
            command,
            environment,
            "web",
            "start",
            "--mode",
            "detached",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        )
        pid = int(pid_file.read_text())
        assert pid > 0
        await wait_for_http(port)
        output = await run_cli(command, environment, "web", "stop")
        assert "stopped" in output.lower()
        assert not pid_file.exists()

        async with asyncio.timeout(10):
            while True:
                try:
                    if psutil.Process(pid).status() == psutil.STATUS_ZOMBIE:
                        break
                except psutil.NoSuchProcess:
                    # Exit can race either process construction or the status read.
                    break
                await asyncio.sleep(0.05)
    finally:
        if pid is None and pid_file.exists():
            pid = int(pid_file.read_text())
        if pid is not None:
            try:
                child = psutil.Process(pid)
                arguments = child.cmdline()
                if "bedrock_server_manager" in arguments and str(config) in arguments:
                    child.terminate()
                    await asyncio.to_thread(child.wait, timeout=10)
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                pass


async def test_foreground_runtime_shutdown_exits_cleanly(web_process_config, tmp_path):
    from bedrock_server_manager.web.control import ControlRecord

    config, command, environment, port = web_process_config
    log = tmp_path / "graceful-web.log"
    with log.open("wb") as output:
        process = await asyncio.create_subprocess_exec(
            *command,
            "web",
            "start",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            env=environment,
            stdout=output,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            await wait_for_http(port, process)
            record = ControlRecord.model_validate_json(
                (config / "web_server.control.json").read_text()
            )
            async with AsyncClient(timeout=5, trust_env=False) as client:
                response = await client.post(
                    record.url,
                    json={},
                    headers={"X-BSM-Shutdown-Token": record.token.get_secret_value()},
                )
                assert response.status_code == 202
                assert response.json()["instance_id"] == record.instance_id
            await asyncio.wait_for(process.wait(), 20)
            assert process.returncode == 0, log.read_text(errors="replace")
            assert "Application shutdown complete" in log.read_text()
            assert not (config / "web_server.pid").exists()
            assert not (config / "web_server.control.json").exists()
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
