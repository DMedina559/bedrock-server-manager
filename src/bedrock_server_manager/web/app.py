"""Compose the web application, registered routers, and plugin extensions."""

from fastapi import FastAPI

from ..api.models.common import ErrorEnvelope
from ..config import get_installed_version
from ..context import AppContext
from . import routers
from .access_metadata import configure_access_schema, validate_core_access
from .access_policy import AccessPolicy
from .errors import configure_errors
from .lifespan import application_lifespan
from .middleware.configure import DEFAULT_ORIGINS, configure_middleware
from .openapi_tags import OPENAPI_TAGS
from .runtime import WebRuntime
from .static import mount_static
from .swagger import configure_swagger


def create_web_app(
    app_context: AppContext, runtime: WebRuntime | None = None
) -> FastAPI:
    """Build the web application without starting runtime services."""
    app = FastAPI(
        title="Bedrock Server Manager",
        version=get_installed_version(),
        redoc_url=None,
        docs_url=None,
        openapi_url="/api/openapi.json",
        openapi_tags=OPENAPI_TAGS,
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "filter": True,
            "deepLinking": True,
        },
        lifespan=application_lifespan(app_context, runtime),
        responses={
            code: {"model": ErrorEnvelope}
            for code in (400, 401, 403, 404, 409, 422, 500, 503)
        },
    )
    configure_errors(app)
    app.state.app_context = app_context
    app.state.web_runtime = runtime
    app_context._web_runtime = runtime
    mount_static(app, app_context.settings.get("paths.themes"))
    configure_middleware(
        app,
        app_context.settings.get("web.cors_origins", DEFAULT_ORIGINS),
        app_context.settings.get("web.forwarded_allow_ips", "127.0.0.1"),
    )
    for router in routers.all_routers:
        app.include_router(router)
    app.state.access_policy = getattr(
        app_context.plugin_manager, "access_policy", AccessPolicy()
    )
    app.state.access_policy.bind_schema(app)
    validate_core_access(app, app.state.access_policy)
    configure_access_schema(app, app.state.access_policy)
    configure_swagger(app)
    app_context.plugin_manager.bind_web_app(app)
    return app
