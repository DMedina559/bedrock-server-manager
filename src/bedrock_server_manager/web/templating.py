# bedrock_server_manager/web/templating.py
import os
from fastapi.templating import Jinja2Templates
from typing import Optional

from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.config.const import get_installed_version

templates: Optional[Jinja2Templates] = None


def configure_templates(templates_instance: Jinja2Templates):
    """
    Configures the Jinja2Templates instance with global variables and filters.
    This function should be called exactly once from the main application entry point (e.g., main.py)
    to set up the single, shared templates instance for the entire application.

    Args:
        templates_instance (Jinja2Templates): The Jinja2Templates instance created in the main app.
    """
    global templates

    templates = templates_instance

    templates.env.filters["basename"] = os.path.basename

    templates.env.globals["app_name"] = settings.get(
        "app.name", "Bedrock Server Manager"
    )
    templates.env.globals["app_version"] = get_installed_version()
    templates.env.globals["splash_text"] = settings.get(
        "web.splash_text", "It's Web Based!"
    )
    templates.env.globals["panorama_url"] = settings.get("web.panorama_url", "")


def get_templates() -> Jinja2Templates:
    """
    Provides access to the globally configured Jinja2Templates instance.
    This function should be used by routers and other modules that need to render templates.

    Returns:
        Jinja2Templates: The configured Jinja2Templates instance.

    Raises:
        RuntimeError: If the templates instance has not been configured yet (i.e.,
                      configure_templates() was not called from the main app).
    """
    if templates is None:

        raise RuntimeError(
            "Jinja2Templates instance has not been configured. Call configure_templates() first from your main application entry point."
        )
    return templates
