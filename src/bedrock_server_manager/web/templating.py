# bedrock_server_manager/web/templating.py
"""Manages the Jinja2 templating environment for the FastAPI web application.

This module provides functions to configure and access a global
:class:`fastapi.templating.Jinja2Templates` instance. This instance is
used throughout the web application for rendering HTML templates.

It allows setting global variables (e.g., application name, version) and
custom filters (e.g., ``basename``) that are available to all templates.
The :func:`~.configure_templates` function should be called once during
application startup, and :func:`~.get_templates` is used by route handlers
to obtain the configured templates object.
"""
import os
from fastapi.templating import Jinja2Templates
from typing import Optional, List
from pathlib import Path

from ..utils import get_utils
from ..config import get_installed_version, app_name_title

templates: Optional[Jinja2Templates] = None


def configure_templates(template_directories: List[Path]):
    """
    Creates and configures the global Jinja2Templates instance.

    This function should be called exactly once from the main application startup
    sequence (e.g., in ``main.py``) to initialize the templating system.
    It creates the Jinja2Templates instance with the provided list of directories
    and sets global variables and filters.

    Args:
        template_directories (List[Path]): A list of `pathlib.Path` objects,
            each pointing to a directory to be included in Jinja2's search path.
            The order matters for template overriding (first found wins).
    """
    global templates

    if not template_directories:
        raise ValueError("At least one template directory must be provided.")

    templates = Jinja2Templates(directory=template_directories)

    # Add custom filters
    templates.env.filters["basename"] = os.path.basename

    # Add global variables
    from ..instances import get_settings_instance

    templates.env.globals["app_name"] = app_name_title
    templates.env.globals["app_version"] = get_installed_version()
    templates.env.globals["splash_text"] = get_utils._get_splash_text()
    templates.env.globals["panorama_url"] = "/api/panorama"
    templates.env.globals["settings"] = get_settings_instance()


def get_templates() -> Jinja2Templates:
    """
    Provides access to the globally configured Jinja2Templates instance.

    This function should be used by FastAPI route handlers and other parts of
    the web application that need to render HTML templates.

    Returns:
        :class:`~fastapi.templating.Jinja2Templates`: The configured global
        Jinja2Templates instance.

    Raises:
        RuntimeError: If the templates instance has not been configured yet
            (i.e., :func:`~.configure_templates` was not called during
            application startup).
    """
    if templates is None:

        raise RuntimeError(
            "Jinja2Templates instance has not been configured. Call configure_templates() first from your main application entry point."
        )
    return templates
