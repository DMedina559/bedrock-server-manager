"""Compose HTTP middleware in a stable execution order."""

import logging
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import add_user_to_request
from .ingress import IngressMiddleware
from .lifecycle import reject_new_mutations
from .setup import setup_check_middleware

logger = logging.getLogger(__name__)
DEFAULT_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def configure_middleware(app: FastAPI, origins: Any) -> None:
    """Register ingress, CORS, identity, setup, and shutdown admission layers."""
    app.middleware("http")(reject_new_mutations)
    allowed_origins = origins

    # If user provided a string (e.g. "*"), wrap it in a list
    if isinstance(allowed_origins, str):
        allowed_origins = [allowed_origins]

    if not isinstance(allowed_origins, list):
        allowed_origins = []

    # allow_credentials=True cannot be used with allow_origins=["*"] in CORS.
    # If "*" is present, we use allow_origin_regex=".*" to dynamically reflect the origin.
    allow_all_origins = "*" in allowed_origins

    logger.debug("CORS Allowed Origins: %s", allowed_origins)

    app.middleware("http")(setup_check_middleware)
    app.middleware("http")(add_user_to_request)

    # Add CORS Middleware
    cors_kwargs: dict[str, Any] = {
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }

    if allow_all_origins:
        cors_kwargs["allow_origin_regex"] = ".*"
    else:
        cors_kwargs["allow_origins"] = allowed_origins

    app.add_middleware(CORSMiddleware, **cors_kwargs)

    # Add ASGI middleware for Ingress support (executes first)
    app.add_middleware(IngressMiddleware)
