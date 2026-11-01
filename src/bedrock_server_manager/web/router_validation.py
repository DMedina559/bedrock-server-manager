"""Validate the effective route contract before publishing plugin routes."""

import re

from fastapi import FastAPI


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
    candidate = FastAPI()
    candidate.router.routes[:] = list(base_routes)
    for router in routers:
        candidate.include_router(router)
    validate_route_contract(candidate)
    if policy is not None:
        from .access_metadata import access_for, api_routes

        for route in api_routes(candidate):
            metadata = access_for(route, policy)
            policy.validate(metadata["required_permissions"])
            for alternative in metadata.get("credential_alternatives", []):
                policy.validate(alternative["permissions"])
