import logging

from ..context import AppContext
from ..core.server.properties import (
    _validate_properties_payload,
)
from ..core.server.properties import (
    validate_property_value as _core_validate_property_value,
)
from ..error import (
    AppFileNotFoundError,
    BSMError,
    UserInputError,
)
from ..events import trigger_event
from ..logging import log_operation_error
from ..plugins.api_bridge import api_method
from .models.properties import (
    GetPropertiesRequest,
    GetPropertiesResponse,
    GetRawPropertiesRequest,
    GetRawPropertiesResponse,
    SetPropertiesRequest,
    SetPropertiesResponse,
    ValidatePropertyValueRequest,
    ValidatePropertyValueResponse,
)
from .server import server_lifecycle_manager

logger = logging.getLogger(__name__)


@api_method("get_properties")
async def get_properties(
    request: GetPropertiesRequest, *, app_context: AppContext
) -> GetPropertiesResponse:
    """Return the current server properties for a given server."""
    server_name = request.server_name
    import aiofiles

    try:
        server = app_context.get_server(server_name)
        properties = await server.properties.get_server_properties()
        raw_content = ""
        async with aiofiles.open(
            server.paths.server_properties_path, "r", encoding="utf-8"
        ) as f:
            raw_content = await f.read()
        return GetPropertiesResponse.model_validate(
            {"status": "success", "properties": properties, "raw_content": raw_content}
        )
    except AppFileNotFoundError:
        raise
    except BSMError as e:
        log_operation_error(
            logger, "Failed to get properties for '%s': %s", server_name, e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error getting properties for '%s': %s",
            server_name,
            e,
            error=e,
        )
        raise


@api_method("get_raw_properties")
async def get_raw_properties(
    request: GetRawPropertiesRequest, *, app_context: AppContext
) -> GetRawPropertiesResponse:
    """Read the complete properties document without parsing its keys or comments."""
    import aiofiles

    server = app_context.get_server(request.server_name)
    async with aiofiles.open(
        server.paths.server_properties_path, "r", encoding="utf-8"
    ) as source:
        content = await source.read()
    return GetRawPropertiesResponse(raw_content=content)


@api_method("validate_property_value")
def validate_property_value(
    request: ValidatePropertyValueRequest,
) -> ValidatePropertyValueResponse:
    """Validates a specific server property value before it gets applied."""
    return _core_validate_property_value(request)


@api_method("set_properties")
@trigger_event(
    before="before_properties_change",
    after="after_properties_change",
    identity_keys=("server_name",),
)
async def set_properties(
    request: SetPropertiesRequest, *, app_context: AppContext
) -> SetPropertiesResponse:
    """Set one or multiple server properties for a given server."""
    server_name = request.server_name
    properties_to_update = request.properties_to_update
    restart_after_modify = request.restart_after_modify
    if not isinstance(properties_to_update, dict):
        raise TypeError("Properties must be a dict.")
    try:
        _validate_properties_payload(properties_to_update)
        async with server_lifecycle_manager(
            server_name,
            stop_before=restart_after_modify,
            restart_on_success_only=True,
            app_context=app_context,
        ):
            server = app_context.get_server(server_name)
            for prop_name, prop_value in properties_to_update.items():
                await server.properties.set_server_property(prop_name, prop_value)
        return SetPropertiesResponse(
            server_name=server_name,
            status="success",
            message="Server properties updated successfully.",
        )
    except (BSMError, FileNotFoundError, UserInputError) as e:
        log_operation_error(
            logger, "Failed to modify properties for '%s': %s", server_name, e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error modifying properties for '%s': %s",
            server_name,
            e,
            error=e,
        )
        raise
