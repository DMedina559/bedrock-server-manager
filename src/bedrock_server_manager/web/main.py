"""Compose one Uvicorn server and own its runtime/control-file lifetime."""

import logging

import uvicorn

from ..context import AppContext
from ..logging import configure_web_logging
from ..services.lifecycle import LifecyclePhase
from .app import create_web_app
from .control import ControlFiles
from .runtime import WebRunOptions, WebRuntime

logger = logging.getLogger(__name__)


def create_server(
    app_context: AppContext, options: WebRunOptions, runtime: WebRuntime
) -> uvicorn.Server:
    settings = app_context.settings
    host = options.host or settings.get("web.host", "127.0.0.1")
    port = options.port or settings.get("web.port", 11325)
    app = create_web_app(app_context, runtime)
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_config=None,
        log_level="debug" if options.debug else None,
        access_log=True,
        workers=1,
        forwarded_allow_ips=settings.get("web.forwarded_allow_ips", "127.0.0.1"),
        proxy_headers=False,
        timeout_graceful_shutdown=settings.get(
            "lifecycle.request_drain_timeout_seconds", 10.0
        ),
        lifespan="on",
    )
    configure_web_logging()
    server = uvicorn.Server(config)
    runtime.attach(lambda: setattr(server, "should_exit", True))
    return server


def run_web_server(
    app_context: AppContext,
    host: str | None = None,
    port: int | None = None,
    debug: bool = False,
    *,
    runtime: WebRuntime | None = None,
    instance_id: str | None = None,
) -> None:
    options = WebRunOptions(host=host, port=port, debug=debug, instance_id=instance_id)
    runtime = runtime or WebRuntime(options.instance_id)
    control = ControlFiles(app_context.config_dir, runtime)
    control.acquire()
    failed = False
    try:
        server = create_server(app_context, options, runtime)
        runtime.on_ready = lambda: control.publish(
            server.config.host, server.config.port
        )
        logger.info(
            "Web server starting at http://%s:%s.",
            server.config.host,
            server.config.port,
        )
        server.run()
        if not server.started and not runtime.snapshot().shutdown_requested:
            raise RuntimeError("Web server failed to start")
        if app_context.lifecycle_phase == LifecyclePhase.FAILED:
            raise RuntimeError("Application lifecycle failed")
    except BaseException:
        failed = True
        raise
    finally:
        runtime.finish(failed=failed)
        control.close()
