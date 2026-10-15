"""Mount frontend assets and ingress-aware static directories."""

import logging
import mimetypes
import os
import re

import bsm_frontend
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


class CachedStaticFiles(StaticFiles):
    """Cache fingerprinted bundles permanently; revalidate mutable assets."""

    def __init__(self, *args, cache_bundles=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache_bundles = cache_bundles

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        # Vite emits name-HASH.ext; public assets retain their original names.
        fingerprinted = (
            self.cache_bundles
            and "/" not in path
            and re.search(r"-[A-Za-z0-9_-]{8,}\.(?:js|css)$", path)
        )
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable" if fingerprinted else "no-cache"
        )
        return response


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
                app.mount(
                    url,
                    CachedStaticFiles(
                        directory=directory, cache_bundles=folder == "assets"
                    ),
                    name=name,
                )
            logger.debug("Mounted bsm-frontend %s from %s", folder, directory)
    else:
        logger.warning("bsm-frontend static directory not found at %s", static_dir)
    if os.path.isdir(themes_path):
        app.mount("/themes", CachedStaticFiles(directory=themes_path), name="themes")
