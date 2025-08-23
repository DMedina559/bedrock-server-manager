from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

import os
from pathlib import Path

if TYPE_CHECKING:
    from .config.settings import Settings
    from .core.bedrock_server import BedrockServer
    from .core.manager import BedrockServerManager
    from .plugins.plugin_manager import PluginManager
    from .core.bedrock_process_manager import BedrockProcessManager
    from .db.database import Database
    from .web.tasks import TaskManager
    from fastapi.templating import Jinja2Templates


class AppContext:
    """
    A context object that holds application-wide instances and caches.
    """

    def __init__(
        self,
        settings: Optional["Settings"] = None,
        manager: Optional["BedrockServerManager"] = None,
        db: Optional["Database"] = None,
    ):
        """
        Initializes the AppContext.
        """
        self.settings: Optional["Settings"] = settings
        self.manager: Optional["BedrockServerManager"] = manager
        self._db: Optional["Database"] = db
        self._bedrock_process_manager: Optional["BedrockProcessManager"] = None
        self._plugin_manager: Optional["PluginManager"] = None
        self._task_manager: Optional["TaskManager"] = None
        self._servers: Dict[str, "BedrockServer"] = {}
        self._templates: Optional["Jinja2Templates"] = None

    def load(self):
        """
        Loads the application context by initializing the settings and manager.
        """
        from .config.settings import Settings
        from .core.manager import BedrockServerManager

        self.db.initialize()

        if self.settings is None:
            self.settings = Settings(db=self.db)
            self.settings.load()

        if self.manager is None:
            assert self.settings is not None
            self.manager = BedrockServerManager(self.settings)
            self.manager.load()

    @property
    def db(self) -> "Database":
        """
        Lazily loads and returns the Database instance.
        """
        if self._db is None:
            from .db.database import Database

            self._db = Database()
        return self._db

    @db.setter
    def db(self, value: "Database"):
        """
        Sets the Database instance.
        """
        self._db = value

    @property
    def plugin_manager(self) -> "PluginManager":
        """
        Lazily loads and returns the PluginManager instance.
        """
        if self._plugin_manager is None:
            from .plugins.plugin_manager import PluginManager

            self._plugin_manager = PluginManager(self.settings)
            self._plugin_manager.set_app_context(self)
        return self._plugin_manager

    @plugin_manager.setter
    def plugin_manager(self, value: "PluginManager"):
        """
        Sets the PluginManager instance.
        """
        self._plugin_manager = value

    @property
    def task_manager(self) -> "TaskManager":
        """
        Lazily loads and returns the TaskManager instance.
        """
        if self._task_manager is None:
            from .web.tasks import TaskManager

            self._task_manager = TaskManager()
        return self._task_manager

    @task_manager.setter
    def task_manager(self, value: "TaskManager"):
        """
        Sets the TaskManager instance.
        """
        self._task_manager = value

    @property
    def bedrock_process_manager(self) -> "BedrockProcessManager":
        """
        Lazily loads and returns the BedrockProcessManager instance.
        """
        if self._bedrock_process_manager is None:
            from .core.bedrock_process_manager import BedrockProcessManager

            self._bedrock_process_manager = BedrockProcessManager(app_context=self)
        return self._bedrock_process_manager

    @bedrock_process_manager.setter
    def bedrock_process_manager(self, value: "BedrockProcessManager"):
        """
        Sets the BedrockProcessManager instance.
        """
        self._bedrock_process_manager = value

    @property
    def templates(self) -> "Jinja2Templates":
        """
        Lazily loads and returns the Jinja2Templates instance.
        """
        if self._templates is None:
            from fastapi.templating import Jinja2Templates
            from .config import get_installed_version, app_name_title, SCRIPT_DIR
            from .utils import get_utils

            app_path = os.path.join(SCRIPT_DIR, "web", "app.py")
            APP_ROOT = os.path.dirname(os.path.abspath(app_path))
            TEMPLATES_DIR = os.path.join(APP_ROOT, "templates")

            all_template_dirs = [Path(TEMPLATES_DIR)]
            if self.plugin_manager.plugin_template_paths:
                unique_plugin_paths = {
                    p
                    for p in self.plugin_manager.plugin_template_paths
                    if isinstance(p, Path)
                }
                all_template_dirs.extend(list(unique_plugin_paths))

            self._templates = Jinja2Templates(directory=all_template_dirs)
            self._templates.env.filters["basename"] = os.path.basename
            self._templates.env.globals["app_name"] = app_name_title
            self._templates.env.globals["app_version"] = get_installed_version()
            self._templates.env.globals["splash_text"] = get_utils._get_splash_text()
            self._templates.env.globals["panorama_url"] = "/api/panorama"
            self._templates.env.globals["settings"] = self.settings

        return self._templates

    def get_server(self, server_name: str) -> "BedrockServer":
        """
        Retrieve or create a BedrockServer instance.
        Args:
            server_name: The name of the server to get.
        Returns: The BedrockServer instance.
        """
        from .core.bedrock_server import BedrockServer

        if server_name not in self._servers:
            self._servers[server_name] = BedrockServer(
                server_name, settings_instance=self.settings
            )
        return self._servers[server_name]
