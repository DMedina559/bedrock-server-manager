"""Generate access descriptions from dependency declarations, never URL heuristics."""

from fastapi import FastAPI, routing
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

from .access_policy import ROLE_GRANTS, AccessPolicy
from .authorization import NON_DELEGATABLE
from .deps.auth import (
    get_admin_user,
    get_current_user,
    get_moderator_user,
    require_permissions,
)


def describe_access(
    classification: str,
    *,
    authentication: str = "required",
    additional_checks=(),
    allowed_roles=None,
):
    """Explicitly describe public or contextual policies alongside enforcement."""

    def decorate(endpoint):
        endpoint.__bsm_access__ = {
            "classification": classification,
            "authentication": authentication,
            "additional_checks": list(additional_checks),
        }
        if allowed_roles is not None:
            endpoint.__bsm_access__["allowed_roles"] = list(allowed_roles)
        return endpoint

    return decorate


def dependency_tree(dependant):
    yield dependant
    for child in dependant.dependencies:
        yield from dependency_tree(child)


def api_routes(app):
    # FastAPI 0.162 retains included routers as contexts; earlier releases
    # flatten them into APIRoutes. Use effective dependencies in both cases.
    iterator = getattr(routing, "iter_route_contexts", None)
    if iterator is None:
        yield from (route for route in app.routes if isinstance(route, APIRoute))
    else:
        yield from (
            context
            for context in iterator(app.routes)
            if isinstance(context.original_route, APIRoute)
        )


def access_for(route: APIRoute, policy: AccessPolicy) -> dict:
    nodes = list(dependency_tree(route.dependant))
    calls = [node.call for node in nodes]
    required = sorted(
        {
            scope
            for node in nodes
            if node.call is require_permissions
            for scope in (
                getattr(node, "security_scopes", None)
                or (
                    list(getattr(node, "parent_oauth_scopes", None) or [])
                    + list(getattr(node, "own_oauth_scopes", None) or [])
                )
            )
        }
    )
    legacy_roles = None
    if get_admin_user in calls:
        legacy_roles = {"admin"}
    elif get_moderator_user in calls:
        legacy_roles = {"moderator", "admin"}
    classification = "unknown"
    roles = []
    authentication = "unknown"
    if require_permissions in calls:
        classification, authentication = "permission", "required"
        roles = [role for role in ROLE_GRANTS if set(required) <= policy.resolve(role)]
    elif legacy_roles is not None:
        classification, authentication = "legacy-role", "required"
        roles = [role for role in ROLE_GRANTS if role in legacy_roles]
    elif get_current_user in calls:
        classification, authentication = "authenticated", "required"
        roles = list(ROLE_GRANTS)
    if legacy_roles is not None:
        roles = [role for role in roles if role in legacy_roles]
    metadata = {
        "version": 1,
        "classification": classification,
        "authentication": authentication,
        "required_permissions": required,
        "allowed_roles": roles,
        "additional_checks": [],
    }
    metadata.update(getattr(route.endpoint, "__bsm_access__", {}))
    metadata["integration_tokens"] = (
        "supported"
        if (require_permissions in calls and not (set(required) & NON_DELEGATABLE))
        or getattr(route.endpoint, "__bsm_token_policy__", False)
        else "unsupported"
    )
    metadata["resource_scope"] = (
        "server"
        if "server_name" in route.param_convertors
        else (
            "collection"
            if getattr(route.endpoint, "__bsm_server_collection__", False)
            else "global"
        )
    )
    return metadata


def configure_access_schema(app: FastAPI, policy: AccessPolicy) -> None:
    def schema():
        if app.openapi_schema is not None:
            return app.openapi_schema
        document = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
            servers=app.servers,
            openapi_version=app.openapi_version,
        )
        for route in api_routes(app):
            if not route.include_in_schema:
                continue
            metadata = access_for(route, policy)
            for method in sorted(route.methods):
                operation = document["paths"][route.path_format][method.lower()]
                operation["x-bsm-access"] = metadata
                # Cookie credentials authorize the same capabilities, but API keys
                # cannot carry OAuth scopes. Preserve all alternative schemes.
                if metadata["integration_tokens"] == "unsupported":
                    operation["security"] = [
                        alternative
                        for alternative in operation.get("security", [])
                        if "IntegrationToken" not in alternative
                    ]
                for alternative in operation.get("security", []):
                    if "IntegrationToken" in alternative:
                        alternative["IntegrationToken"] = []
                    if "APIKeyCookie" in alternative:
                        alternative["APIKeyCookie"] = []
        schemes = document.get("components", {}).get("securitySchemes", {})
        if "OAuth2PasswordBearer" in schemes:
            schemes["OAuth2PasswordBearer"]["flows"]["password"][
                "scopes"
            ] = policy.descriptions
        app.openapi_schema = document
        return document

    setattr(app, "openapi", schema)


def validate_core_access(app: FastAPI, policy: AccessPolicy) -> None:
    """Reject unknown core scopes and missing classifications during construction."""
    for route in api_routes(app):
        if not route.include_in_schema:
            continue
        metadata = access_for(route, policy)
        policy.validate(metadata["required_permissions"])
        if metadata["classification"] == "unknown":
            raise ValueError(
                f"Core operation lacks access policy: {route.operation_id}"
            )
