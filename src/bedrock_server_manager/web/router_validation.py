"""Validate the effective route contract before publishing plugin routes."""

import logging
import re

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def validate_route_contract(app):
    from .access_metadata import api_routes

    identifiers, bindings = set(), set()
    for route in api_routes(app):
        for method in route.methods:
            binding = (method, re.sub(r"\(\?P<[^>]+>", "(", route.path_regex.pattern))
            if binding in bindings:
                raise ValueError(f"Duplicate HTTP route: {method} {route.path}")
            bindings.add(binding)
        if not route.include_in_schema:
            continue
        identifier = route.operation_id or route.unique_id
        if not identifier or identifier in identifiers:
            raise ValueError(f"Missing or duplicate operationId: {identifier}")
        identifiers.add(identifier)


def validate_plugin_routes(base_routes, routers, policy=None):
    from .access_metadata import access_for, api_routes, uses_legacy_role

    candidate = FastAPI()
    candidate.router.routes[:] = list(base_routes)
    base_bindings = {
        (route.path, frozenset(route.methods)) for route in api_routes(candidate)
    }
    for router in routers:
        candidate.include_router(router)
    validate_route_contract(candidate)
    if policy is not None:
        for route in api_routes(candidate):
            metadata = access_for(route, policy)
            policy.validate(metadata["required_permissions"])
            for alternative in metadata.get("credential_alternatives", []):
                policy.validate(alternative["permissions"])
            if (
                uses_legacy_role(route)
                and (route.path, frozenset(route.methods)) not in base_bindings
            ):
                logger.warning(
                    "Plugin route '%s' uses deprecated legacy role dependencies (get_admin_user / get_moderator_user); use 'Security(require_permissions, scopes=[...])' instead.",
                    route.path,
                )
