"""Host the web runtime as a Windows SCM service using pywin32."""

import logging
import os
import sys
import threading
from pathlib import Path

from ..logging import log_operation_error

try:
    import pywintypes
    import servicemanager
    import win32file
    import win32pipe
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

logger = logging.getLogger(__name__)


class WebServerWindowsService(win32serviceutil.ServiceFramework):
    """Manage the application's Web UI as a self-sufficient Windows Service."""

    # These are placeholders; the CLI wrapper will set the real names.
    _svc_name_ = "BSMWebUIService"
    _svc_display_name_ = "Bedrock Server Manager Web UI"
    _svc_description_ = "Hosts the web interface for the Bedrock Server Manager."
    app_context = None

    def __init__(self, args):
        """Initialize service identity and shutdown coordination.

        :param args: Arguments supplied by the Windows service dispatcher.
        """
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.shutdown_event = threading.Event()
        from .runtime import WebRuntime

        self.runtime = WebRuntime()
        self.logger = logging.getLogger(__name__)

        # The first arg from HandleCommandLine is always the service name.
        if args:
            self._svc_name_ = args[0]

        # --- The service is now self-sufficient ---

    def SvcStop(self):
        """Called by the SCM when the service is stopping."""
        self.logger.info("Web Service '%s': Stop request received.", self._svc_name_)
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        try:
            self.runtime.request_shutdown("service")
        except Exception as e:
            log_operation_error(self.logger, "Error sending stop: %s", e, error=e)
        self.shutdown_event.set()  # Signal the main loop to exit

    def SvcDoRun(self):
        """The main service entry point."""
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)

        failed = False
        try:
            from .main import run_web_server

            if getattr(sys, "frozen", False):
                # If running as a frozen exe (e.g., PyInstaller)
                script_dir = os.path.dirname(sys.executable)
            else:
                # If running as a normal .py script
                script_dir = str(Path(__file__).resolve().parents[3])

            os.chdir(script_dir)
            # --- The service runs the web app DIRECTLY in a thread ---
            self.logger.debug("Starting web server logic in a background thread.")

            failures = []

            def serve():
                try:
                    run_web_server(self.app_context, runtime=self.runtime)
                except BaseException as error:
                    failures.append(error)
                finally:
                    self.shutdown_event.set()

            web_thread = threading.Thread(
                target=serve,
                daemon=False,
            )
            web_thread.start()

            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            self.logger.debug(
                "Web Service '%s': Status reported as RUNNING.", self._svc_name_
            )

            # Wait loop that also checks if the web thread crashes.
            while not self.shutdown_event.is_set():
                # Wait for 1 second, then check if thread is still alive
                self.shutdown_event.wait(1.0)
                if not web_thread.is_alive() and not self.shutdown_event.is_set():
                    raise RuntimeError("Web server thread unexpectedly terminated.")

            self.logger.debug(
                "Web Service '%s': Shutdown event processed. Waiting for web thread to close...",
                self._svc_name_,
            )
            # Give request draining and application cleanup the same deadline as systemd.
            wait_time = 0
            while web_thread.is_alive() and wait_time < 180:
                # Keep reporting STOP_PENDING so the SCM doesn't kill us
                self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
                web_thread.join(timeout=1.0)
                wait_time += 1
            if web_thread.is_alive():
                raise RuntimeError(
                    "Web runtime did not stop within the service deadline"
                )
            if failures:
                raise RuntimeError("Web runtime failed") from failures[0]

        except Exception as e:
            failed = True
            log_operation_error(
                self.logger,
                "Web Service '%s': FATAL ERROR in SvcDoRun: %s",
                self._svc_name_,
                e,
                error=e,
            )
            if PYWIN32_AVAILABLE and servicemanager:
                try:
                    servicemanager.LogErrorMsg(
                        f"Web Service '{self._svc_name_}' FATAL ERROR: {str(e)}"
                    )
                except Exception:
                    pass
        finally:
            self.ReportServiceStatus(
                win32service.SERVICE_STOPPED,
                win32ExitCode=1066 if failed else 0,
                svcExitCode=1 if failed else 0,
            )
            self.logger.debug(
                "Web Service '%s': Status reported as STOPPED.", self._svc_name_
            )
