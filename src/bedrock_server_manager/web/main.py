"""
Main application file for the Bedrock Server Manager web UI.
"""

from ..app_context import create_web_app
from ..instances import get_settings_instance

# Get the settings instance
settings = get_settings_instance()

# Create the FastAPI app
app = create_web_app(settings)

if __name__ == "__main__":
    import uvicorn
    from uvicorn.config import LOGGING_CONFIG

    # To prevent uvicorn from taking over the logger, we need to disable it.
    # More info: https://github.com/encode/uvicorn/issues/1285
    LOGGING_CONFIG["loggers"]["uvicorn"]["propagate"] = True

    uvicorn.run(app, host="127.0.0.1", port=11325, log_config=LOGGING_CONFIG)
