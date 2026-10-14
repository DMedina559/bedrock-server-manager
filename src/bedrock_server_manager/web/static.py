"""Mount frontend assets and ingress-aware static directories."""

import logging
import mimetypes
import os

import bsm_frontend
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


class IngressAwareStaticFiles(StaticFiles):
    """Strip the ingress prefix for static lookup, then restore the request scope."""

    async def __call__(self, scope, receive, send):
        original_root_path = scope.get("root_path", "")

        ingress_path = ""
        headers = dict(scope.get("headers", []))
        if b"x-ingress-path" in headers:
            ingress_path = headers[b"x-ingress-path"].decode("latin-1")

            if original_root_path.startswith(ingress_path):
                scope["root_path"] = original_root_path[
                    len(ingress_path) :  # noqa: E203
                ]

        try:
            await super().__call__(scope, receive, send)
        finally:
            scope["root_path"] = original_root_path


def mount_static(app: FastAPI, themes_path: str) -> None:
    """Mount available frontend assets and configured custom themes."""
    mimetypes.add_type("application/javascript", ".js")
    static_dir = bsm_frontend.get_static_dir()
    if os.path.isdir(static_dir):
        for folder, mounts in (
            ("assets", (("/app/assets", "app_assets"),)),
            ("image", (("/app/image", "app_images"), ("/image", "root_images"))),
        ):
            directory = os.path.join(static_dir, folder)
            if not os.path.isdir(directory):
                logger.warning(
                    "bsm-frontend '%s' subdirectory not found at %s", folder, directory
                )
                continue
            for url, name in mounts:
                app.mount(url, IngressAwareStaticFiles(directory=directory), name=name)
            logger.debug("Mounted bsm-frontend %s from %s", folder, directory)
    else:
        logger.warning("bsm-frontend static directory not found at %s", static_dir)
    if os.path.isdir(themes_path):
        app.mount(
            "/themes", IngressAwareStaticFiles(directory=themes_path), name="themes"
        )
