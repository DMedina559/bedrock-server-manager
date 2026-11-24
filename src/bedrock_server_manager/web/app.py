"""Compose the web application, registered routers, and plugin extensions."""

from fastapi import FastAPI
from starlette.routing import BaseRoute

from ..config import get_installed_version
from ..context import AppContext
from ..models.common import ErrorEnvelope
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

_CORE_ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    code: {"model": ErrorEnvelope}
    for code in (400, 401, 403, 404, 409, 422, 429, 500, 503)
}
_CORE_ROUTER_CACHE: tuple[tuple[object, ...], list[BaseRoute]] | None = None


def _get_core_routes() -> list[BaseRoute]:
    global _CORE_ROUTER_CACHE
    signature = tuple(routers.all_routers)
    if _CORE_ROUTER_CACHE is None or _CORE_ROUTER_CACHE[0] != signature:
        template = FastAPI(
            redoc_url=None,
            docs_url=None,
            openapi_url=None,
            openapi_tags=OPENAPI_TAGS,
            responses=_CORE_ERROR_RESPONSES,
        )
        for router in signature:
            template.include_router(router)
        validate_core_access(template, AccessPolicy())
        _CORE_ROUTER_CACHE = (signature, list(template.router.routes))
    return list(_CORE_ROUTER_CACHE[1])


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
        responses=_CORE_ERROR_RESPONSES,
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
    app.router.routes.extend(_get_core_routes())
    app.state.access_policy = getattr(
        app_context.plugin_manager, "access_policy", AccessPolicy()
    )
    app.state.access_policy.bind_schema(app)
    configure_access_schema(app, app.state.access_policy)
    configure_swagger(app)
    app_context.plugin_manager.bind_web_app(app)
    return app
