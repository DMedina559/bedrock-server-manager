import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class EventPayload(BaseModel):
    event_name: str = Field(
        ..., description="The name of the event to send (e.g. namespace:event_name)"
    )
    args_json: str = Field("[]", description="A JSON array of positional arguments")
    kwargs_json: str = Field("{}", description="A JSON object of keyword arguments")


def define_routes(router: APIRouter, plugin_instance):
    @router.get(
        "/ui",
        response_class=JSONResponse,
        name="Event Sender",
        tags=["plugin-ui-native"],
    )
    async def get_ui(request: Request):
        return JSONResponse(
            content={
                "type": "Container",
                "props": {"style": {"gap": "1rem", "padding": "1rem"}},
                "children": [
                    {
                        "type": "Text",
                        "props": {"content": "Event Sender", "variant": "h1"},
                    },
                    {
                        "type": "Text",
                        "props": {
                            "content": "Trigger custom plugin events easily via this native UI.",
                            "variant": "body",
                        },
                    },
                    {
                        "type": "Card",
                        "props": {"title": "Send an Event"},
                        "children": [
                            {
                                "type": "Container",
                                "props": {
                                    "style": {
                                        "gap": "1rem",
                                        "display": "flex",
                                        "flexDirection": "column",
                                    }
                                },
                                "children": [
                                    {
                                        "type": "Input",
                                        "props": {
                                            "name": "event_name",
                                            "label": "Event Name",
                                            "placeholder": "e.g., myplugin:custom_event",
                                            "required": True,
                                        },
                                    },
                                    {
                                        "type": "Input",
                                        "props": {
                                            "name": "args_json",
                                            "label": "Arguments (JSON Array)",
                                            "placeholder": '["arg1", "arg2"]',
                                            "defaultValue": "[]",
                                        },
                                    },
                                    {
                                        "type": "Input",
                                        "props": {
                                            "name": "kwargs_json",
                                            "label": "Keyword Arguments (JSON Object)",
                                            "placeholder": '{"key1": "value1"}',
                                            "defaultValue": "{}",
                                        },
                                    },
                                    {
                                        "type": "Button",
                                        "props": {
                                            "label": "Send Event",
                                            "icon": "Play",
                                            "variant": "primary",
                                            "onClickAction": {
                                                "type": "api_call",
                                                "endpoint": "/api/plugins/event_sender/trigger",
                                                "includeFormState": True,
                                                "refresh": False,
                                            },
                                        },
                                    },
                                ],
                            }
                        ],
                    },
                ],
            }
        )

    @router.post("/trigger")
    async def trigger_event(payload: EventPayload):
        plugin_instance.logger.info(
            f"Received request to trigger event: {payload.event_name}"
        )
        try:
            args = json.loads(payload.args_json)
            if not isinstance(args, list):
                return JSONResponse(
                    status_code=400, content={"error": "args_json must be a JSON array"}
                )

            kwargs = json.loads(payload.kwargs_json)
            if not isinstance(kwargs, dict):
                return JSONResponse(
                    status_code=400,
                    content={"error": "kwargs_json must be a JSON object"},
                )

            plugin_instance.api.send_event(payload.event_name, *args, **kwargs)
            return JSONResponse(
                content={
                    "message": f"Successfully triggered event '{payload.event_name}'"
                }
            )
        except json.JSONDecodeError as e:
            plugin_instance.logger.error(f"Failed to parse JSON payload: {e}")
            return JSONResponse(
                status_code=400, content={"error": f"Invalid JSON format: {e}"}
            )
        except Exception as e:
            plugin_instance.logger.error(f"Error triggering event: {e}")
            return JSONResponse(
                status_code=500, content={"error": f"Failed to trigger event: {e}"}
            )
