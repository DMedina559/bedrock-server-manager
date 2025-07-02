# bedrock_server_manager/core/system/windows_class.py
"""Provides Windows-specific implementations for system interactions.

This module includes functions for:

    - Starting the Bedrock server process directly in the foreground.
    - Managing a named pipe server for inter-process communication (IPC) to send
      commands to the running Bedrock server.
    - Handling OS signals for graceful shutdown of the foreground server.
    - Sending commands to the server via the named pipe.
    - Stopping the server process by PID.
    - Creating, managing, and deleting Windows Services to run the server in the
      background, which requires Administrator privileges.

It relies on the pywin32 package for named pipe and service
functionality.
"""
import os
import sys
import threading
import time
import subprocess
import logging
import re
from typing import Optional, Dict, Any, List

# Third-party imports. pywin32 is optional but required for IPC.
try:
    import win32service
    import win32serviceutil

    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False
    win32pipe = None
    win32file = None
    win32service = None
    win32serviceutil = None
    pywintypes = None

# Local application imports.
from bedrock_server_manager.core.system import process as core_process
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.api.web import start_web_server_api, stop_web_server_api
from bedrock_server_manager.core.system.windows import _main_pipe_server_listener_thread

logger = logging.getLogger(__name__)

# --- Constants ---
BEDROCK_EXECUTABLE_NAME = "bedrock_server.exe"
PIPE_NAME_TEMPLATE = r"\\.\pipe\BedrockServerPipe_{server_name}"

# A global dictionary to keep track of running server processes and their control objects.
# This is used to manage the state of servers started in the foreground.
managed_bedrock_servers: Dict[str, Dict[str, Any]] = {}


# --- WINDOWS SERVICE IMPLEMENTATION ---
class BedrockServerWindowsService(win32serviceutil.ServiceFramework):
    """
    A pywin32 ServiceFramework class to properly manage the server as a service.
    This version includes robust logging and environment setup to handle
    the restrictive context in which Windows Services run.
    """

    _svc_name_ = "BedrockServerWindowsService_Base"
    _svc_display_name_ = "Bedrock Server Manager Service"
    _svc_description_ = "Manages a Minecraft Bedrock Server instance."

    def __init__(self, args):
        """
        The service's constructor. This should be as lightweight as possible.
        Heavy initialization should be deferred to SvcDoRun.
        """
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.shutdown_event = threading.Event()
        self.bedrock_process: Optional[subprocess.Popen] = None
        self.logger = None  # Will be initialized in SvcDoRun

        # The first arg from the SCM is always the service name.
        if args:
            self._svc_name_ = args[0]
            self.server_name = self._svc_name_.replace("bedrock-", "", 1)
        else:
            # This case should not happen in a real service start.
            self.server_name = "unknown_service"

    def emergency_log(self, message: str):
        """A foolproof logger that writes to a public temp file."""
        try:
            # C:\tmp is a common, publicly writable directory.
            os.makedirs(r"C:\tmp", exist_ok=True)
            with open(r"C:\tmp\service_debug.log", "a") as f:
                f.write(
                    f"{time.strftime('%Y-%m-%d %H:%M:%S')} - SVC({self._svc_name_}): {message}\n"
                )
        except Exception:
            # If even this fails, there's nothing more we can do.
            pass

    def SvcStop(self):
        """Called by the SCM when the service is stopping."""
        self.emergency_log("Stop request received.")
        if self.logger:
            self.logger.info(f"Service '{self._svc_name_}': Stop request received.")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.shutdown_event.set()

    def SvcDoRun(self):
        """The main service entry point, containing all startup and running logic."""
        # --- Stage 1: Initial Setup (Pre-Logging) ---
        try:
            if getattr(sys, "frozen", False):
                # If running as a frozen exe (e.g., PyInstaller)
                script_dir = os.path.dirname(sys.executable)
            else:
                # If running as a normal .py script
                script_dir = os.path.dirname(os.path.realpath(__file__))

            os.chdir(script_dir)
            self.emergency_log(
                f"SvcDoRun started. Working directory set to: {script_dir}"
            )
        except Exception as e:
            self.emergency_log(
                f"CRITICAL FAILURE: Could not set working directory. Error: {e}"
            )
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
            return

        # --- Stage 2: Main Application Logic ---
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        try:
            # Now that the CWD is correct, the main logging system should initialize correctly.
            self.logger = logging.getLogger(__name__)
            self.logger.info("Main application logging initialized successfully.")

            self.logger.info("Instantiating BedrockServer object.")
            self.server = BedrockServer(self.server_name)
            self._svc_display_name_ = self.server.windows_service_display_name
            self.logger.info("BedrockServer instantiated successfully.")

            server_exe_path = self.server.bedrock_executable_path
            pipe_name = PIPE_NAME_TEMPLATE.format(
                server_name=re.sub(r"\W+", "_", self.server.server_name)
            )
            output_file = self.server.server_log_path
            pid_file_path = self.server.get_pid_file_path()
            self.logger.info(f"Paths prepared. Executable: {server_exe_path}")

            self.logger.info("Attempting to start bedrock_server.exe with Popen.")
            os.makedirs(self.server.server_dir, exist_ok=True)
            log_handle = open(output_file, "ab")
            self.bedrock_process = subprocess.Popen(
                [server_exe_path],
                cwd=self.server.server_dir,
                stdin=subprocess.PIPE,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=False,
                bufsize=0,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.logger.info(
                f"bedrock_server.exe started with PID {self.bedrock_process.pid}."
            )

            self.logger.info("Writing PID file.")
            core_process.write_pid_to_file(pid_file_path, self.bedrock_process.pid)

            self.logger.info("Starting pipe listener thread.")
            pipe_listener_thread = threading.Thread(
                target=_main_pipe_server_listener_thread,
                args=(
                    pipe_name,
                    self.bedrock_process,
                    self.server_name,
                    self.shutdown_event,
                ),
                daemon=True,
            )
            pipe_listener_thread.start()

            self.logger.info("--- ALL STARTUP CHECKS PASSED ---")
            self.logger.info("Reporting SERVICE_RUNNING to SCM.")
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            self.emergency_log("Service status reported as RUNNING.")

            # Service is now running, wait for a stop signal.
            self.shutdown_event.wait()
            self.logger.info("Shutdown event received. Proceeding to cleanup.")

        except Exception as e:
            self.emergency_log(f"FATAL ERROR in SvcDoRun: {e}")
            if self.logger:
                self.logger.error(
                    f"FATAL ERROR in SvcDoRun for service '{self._svc_name_}': {e}",
                    exc_info=True,
                )
            self.SvcStop()

        finally:
            # --- Cleanup Logic ---
            self.emergency_log("Entering cleanup (finally block).")
            if self.logger:
                self.logger.info("Entering service cleanup (finally block).")

            if self.bedrock_process and self.bedrock_process.poll() is None:
                if self.logger:
                    self.logger.info("Sending 'stop' command to Bedrock server.")
                try:
                    if (
                        self.bedrock_process.stdin
                        and not self.bedrock_process.stdin.closed
                    ):
                        self.bedrock_process.stdin.write(b"stop\r\n")
                        self.bedrock_process.stdin.flush()
                        self.bedrock_process.stdin.close()
                    self.bedrock_process.wait(timeout=20)
                except Exception as e:
                    if self.logger:
                        self.logger.warning(
                            f"Graceful stop failed: {e}. Terminating process."
                        )
                    core_process.terminate_process_by_pid(self.bedrock_process.pid)

            if hasattr(self, "server"):
                core_process.remove_pid_file_if_exists(self.server.get_pid_file_path())

            self.emergency_log("Cleanup complete. Reporting STOPPED.")
            if self.logger:
                self.logger.info("Cleanup complete. Reporting STOPPED.")
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)


class WebServerWindowsService(win32serviceutil.ServiceFramework):
    """
    Manages the application's Web UI as a self-sufficient Windows Service.
    """

    # These are placeholders; the CLI wrapper will set the real names.
    _svc_name_ = "BSMWebUIService"
    _svc_display_name_ = "Bedrock Server Manager Web UI"
    _svc_description_ = "Hosts the web interface for the Bedrock Server Manager."

    def __init__(self, args):
        """
        Constructor is simple. It only gets the service name from `args`.
        All other configuration is loaded internally.
        """
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.shutdown_event = threading.Event()
        self.logger = logging.getLogger(__name__)

        # The first arg from HandleCommandLine is always the service name.
        if args:
            self._svc_name_ = args[0]

        # --- The service is now self-sufficient ---

    def SvcStop(self):
        """Called by the SCM when the service is stopping."""
        self.logger.info(f"Web Service '{self._svc_name_}': Stop request received.")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        try:
            stop_web_server_api()
        except Exception as e:
            self.logger.info(f"Error sending stop: {e}")
        self.shutdown_event.set()  # Signal the main loop to exit

    def SvcDoRun(self):
        """The main service entry point."""
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)

        try:
            if getattr(sys, "frozen", False):
                # If running as a frozen exe (e.g., PyInstaller)
                script_dir = os.path.dirname(sys.executable)
            else:
                # If running as a normal .py script
                script_dir = os.path.dirname(os.path.realpath(__file__))

            os.chdir(script_dir)
            # --- The service runs the web app DIRECTLY in a thread ---
            # No more complex subprocess calls.
            self.logger.info(f"Starting web server logic in a background thread.")

            web_thread = threading.Thread(
                target=start_web_server_api,
                kwargs={"mode": "direct"},  # Run in production mode
                daemon=True,
            )
            web_thread.start()

            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            self.logger.info(
                f"Web Service '{self._svc_name_}': Status reported as RUNNING."
            )

            # The service now waits here until SvcStop sets the shutdown_event.
            self.shutdown_event.wait()

            # Optional: Add logic here to gracefully shut down the web server thread if possible.
            self.logger.info(
                f"Web Service '{self._svc_name_}': Shutdown event processed."
            )

        except Exception as e:
            self.logger.error(
                f"Web Service '{self._svc_name_}': FATAL ERROR in SvcDoRun: {e}",
                exc_info=True,
            )
        finally:
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
            self.logger.info(
                f"Web Service '{self._svc_name_}': Status reported as STOPPED."
            )
