# bedrock_server_manager/cli/windows_service.py
import logging
import platform
import sys

import click

if platform.system() == "Windows":
    import win32serviceutil
    import servicemanager
    from ..core.system.windows_class import (
        WebServerWindowsService,
        BedrockServerWindowsService,
        PYWIN32_AVAILABLE,
    )

logger = logging.getLogger(__name__)


@click.group(hidden=True)
def service():
    """Manages the Windows OS service integrations."""
    pass


@service.command(
    "_run-web",
    hidden=True,
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True,
    ),
)
@click.argument("actual_svc_name_arg", type=str)
@click.pass_context
def _run_web_service_windows(ctx, actual_svc_name_arg: str):
    """
    (Internal use only) Clean entry point for the Windows SCM and for debugging the Web UI service.
    """
    if platform.system() != "Windows" or not PYWIN32_AVAILABLE:
        sys.exit(1)

    class WebServiceHandler(WebServerWindowsService):
        _svc_name_ = actual_svc_name_arg
        _svc_display_name_ = f"Bedrock Manager Web UI ({actual_svc_name_arg})"

    if "debug" in ctx.args:
        logger.info(f"Starting Web UI service '{actual_svc_name_arg}' in DEBUG mode.")

        win32serviceutil.DebugService(WebServiceHandler, argv=[actual_svc_name_arg])
    else:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(WebServiceHandler)
        servicemanager.StartServiceCtrlDispatcher()


@service.command(
    "_run-bedrock",
    hidden=True,
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True,
    ),
)
@click.option("-s", "--server", "server_name", required=True)
@click.pass_context
def _run_service(ctx, server_name: str):
    """
    (Internal use only) Entry point for the Windows Service Manager.
    """
    if platform.system() == "Windows" and PYWIN32_AVAILABLE:

        class ServiceHandler(BedrockServerWindowsService):
            _svc_name_ = f"bedrock-{server_name}"
            _svc_display_name_ = f"Bedrock Server ({server_name})"

        if "debug" in ctx.args:
            # Debug mode runs the service logic in the console and blocks.
            logger.info(f"Starting service '{server_name}' in DEBUG mode.")
            win32serviceutil.DebugService(
                ServiceHandler, argv=[f"bedrock-{server_name}"]
            )
        else:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(ServiceHandler)
            servicemanager.StartServiceCtrlDispatcher()
