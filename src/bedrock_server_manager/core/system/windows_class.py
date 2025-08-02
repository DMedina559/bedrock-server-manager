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
from ...api.web import start_web_server_api, stop_web_server_api

logger = logging.getLogger(__name__)


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
                kwargs={"mode": "direct", "threads": 1},  # Run in production mode
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
