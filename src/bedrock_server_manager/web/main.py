# bedrock_server_manager/web/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

from bedrock_server_manager.web import templating

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(APP_ROOT, "templates")
STATIC_DIR = os.path.join(APP_ROOT, "static")

app = FastAPI()

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_templates_instance = Jinja2Templates(directory=TEMPLATES_DIR)

templating.configure_templates(_templates_instance)

from bedrock_server_manager.web.routers import (
    main,
    auth,
    schedule_tasks,
    server_actions,
    server_install_config,
    backup_restore,
    content,
    util,
    settings,
    api_info,
    plugin,
)

app.include_router(main.router)
app.include_router(auth.router)
app.include_router(schedule_tasks.router)
app.include_router(server_actions.router)
app.include_router(server_install_config.router)
app.include_router(backup_restore.router)
app.include_router(content.router)
app.include_router(settings.router)
app.include_router(api_info.router)
app.include_router(plugin.router)
app.include_router(util.router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
