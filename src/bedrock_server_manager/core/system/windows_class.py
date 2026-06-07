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

import logging
import os
import sys
import threading
from pathlib import Path

# typing imports removed as they were unused

# Third-party imports. pywin32 is optional but required for IPC.
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

# Local application imports.
from ...api.web import start_web_server_api

logger = logging.getLogger(__name__)


class WebServerWindowsService(win32serviceutil.ServiceFramework):
    """
    Manages the application's Web UI as a self-sufficient Windows Service.
    """

    # These are placeholders; the CLI wrapper will set the real names.
    _svc_name_ = "BSMWebUIService"
    _svc_display_name_ = "Bedrock Server Manager Web UI"
    _svc_description_ = "Hosts the web interface for the Bedrock Server Manager."
    app_context = None

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
            if (
                hasattr(self.app_context, "_web_server")
                and self.app_context._web_server is not None
            ):
                self.logger.info(f"Instructing Uvicorn to exit gracefully...")
                self.app_context._web_server.should_exit = True
            else:
                self.logger.warning(f"Web server instance not found on app_context.")
        except Exception as e:
            self.logger.error(f"Error sending stop: {e}", exc_info=True)
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
                # Step up from core/system/windows_class.py to the project root
                # bedrock_server_manager -> src -> project root
                script_dir = str(
                    Path(__file__).resolve().parent.parent.parent.parent.parent
                )

            os.chdir(script_dir)
            # --- The service runs the web app DIRECTLY in a thread ---
            # No more complex subprocess calls.
            self.logger.info(f"Starting web server logic in a background thread.")

            web_thread = threading.Thread(
                target=start_web_server_api,
                kwargs={
                    "app_context": self.app_context,
                    "mode": "direct",
                },  # Run in production mode
                daemon=True,
            )
            web_thread.start()

            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            self.logger.info(
                f"Web Service '{self._svc_name_}': Status reported as RUNNING."
            )

            # Wait loop that also checks if the web thread crashes.
            while not self.shutdown_event.is_set():
                # Wait for 1 second, then check if thread is still alive
                self.shutdown_event.wait(1.0)
                if not web_thread.is_alive() and not self.shutdown_event.is_set():
                    raise RuntimeError("Web server thread unexpectedly terminated.")

            self.logger.info(
                f"Web Service '{self._svc_name_}': Shutdown event processed. Waiting for web thread to close..."
            )
            # Give Uvicorn up to 45 seconds to finish open requests and shutdown hooks gracefully
            wait_time = 0
            while web_thread.is_alive() and wait_time < 120:
                # Keep reporting STOP_PENDING so the SCM doesn't kill us
                self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
                web_thread.join(timeout=1.0)
                wait_time += 1

        except Exception as e:
            self.logger.error(
                f"Web Service '{self._svc_name_}': FATAL ERROR in SvcDoRun: {e}",
                exc_info=True,
            )
            if PYWIN32_AVAILABLE and servicemanager:
                try:
                    servicemanager.LogErrorMsg(
                        f"Web Service '{self._svc_name_}' FATAL ERROR: {str(e)}"
                    )
                except Exception:
                    pass
        finally:
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
            self.logger.info(
                f"Web Service '{self._svc_name_}': Status reported as STOPPED."
            )
