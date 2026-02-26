from json import JSONDecodeError
from typing import Any, Dict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from bedrock_server_manager import PluginBase
from bedrock_server_manager.web import get_admin_user


class DynamicPageTestPlugin(PluginBase):
    """
    A plugin to test all Dynamic Page UI components.
    """

    version = "1.0.0"
    author = "dmedina559"

    def on_load(self, **kwargs):
        self.router = APIRouter(tags=["Dynamic Page Test Plugin"])
        self._define_routes()
        self.logger.info(f"Plugin '{self.name}' v{self.version} loaded.")

    def _define_routes(self):
        @self.router.get(
            "/dynamic_page_test/ui",
            response_class=JSONResponse,
            name="Dynamic Page Test UI",
            summary="Test Dynamic Components",
            tags=["plugin-ui-native"],
        )
        async def get_test_ui(
            request: Request, current_user: Dict[str, Any] = Depends(get_admin_user)
        ):
            return JSONResponse(
                content={
                    "websocketSubscriptions": ["server_log:{server}"],
                    "type": "Container",
                    "children": [
                        {
                            "type": "Text",
                            "props": {
                                "content": "Dynamic Page Component Test",
                                "variant": "h1",
                            },
                        },
                        {
                            "type": "Tabs",
                            "props": {"activeTab": 0},
                            "children": [
                                {
                                    "type": "Tab",
                                    "props": {"label": "Form Inputs", "id": 0},
                                    "children": [
                                        {
                                            "type": "Card",
                                            "props": {"title": "Basic Inputs"},
                                            "children": [
                                                {
                                                    "type": "Input",
                                                    "props": {
                                                        "id": "text_input",
                                                        "placeholder": "Text Input",
                                                        "label": "Text Field",
                                                    },
                                                },
                                                {
                                                    "type": "Select",
                                                    "props": {
                                                        "id": "select_input",
                                                        "label": "Select Option",
                                                        "options": [
                                                            {
                                                                "label": "Option A",
                                                                "value": "a",
                                                            },
                                                            {
                                                                "label": "Option B",
                                                                "value": "b",
                                                            },
                                                        ],
                                                    },
                                                },
                                                {
                                                    "type": "Button",
                                                    "props": {
                                                        "label": "Submit Form",
                                                        "onClickAction": {
                                                            "type": "api_call",
                                                            "endpoint": "/api/dynamic_page_test/submit",
                                                            "includeFormState": True,
                                                        },
                                                    },
                                                },
                                            ],
                                        },
                                        {
                                            "type": "Card",
                                            "props": {"title": "Toggle Section"},
                                            "children": [
                                                {
                                                    "type": "Switch",
                                                    "props": {
                                                        "id": "switch_input",
                                                        "label": "Enable Feature",
                                                        "defaultChecked": True,
                                                    },
                                                },
                                                {
                                                    "type": "Checkbox",
                                                    "props": {
                                                        "id": "checkbox_input",
                                                        "label": "I agree to terms",
                                                    },
                                                },
                                            ],
                                        },
                                    ],
                                },
                                {
                                    "type": "Tab",
                                    "props": {"label": "Display & Media", "id": 1},
                                    "children": [
                                        {
                                            "type": "Card",
                                            "props": {"title": "Display Components"},
                                            "children": [
                                                {
                                                    "type": "Row",
                                                    "children": [
                                                        {
                                                            "type": "Badge",
                                                            "props": {
                                                                "content": "New",
                                                                "variant": "success",
                                                            },
                                                        },
                                                        {
                                                            "type": "Badge",
                                                            "props": {
                                                                "content": "Beta",
                                                                "variant": "warning",
                                                            },
                                                        },
                                                    ],
                                                },
                                                {
                                                    "type": "CodeBlock",
                                                    "props": {
                                                        "title": "Example Code",
                                                        "content": "print('Hello World')\nreturn True",
                                                    },
                                                },
                                                {
                                                    "type": "Link",
                                                    "props": {
                                                        "label": "Visit Documentation",
                                                        "href": "https://bedrock-server-manager.readthedocs.io/",
                                                        "target": "_blank",
                                                    },
                                                },
                                            ],
                                        },
                                        {
                                            "type": "Card",
                                            "props": {"title": "Iframe Integration"},
                                            "children": [
                                                {
                                                    "type": "iframe",
                                                    "props": {
                                                        "src": "https://bedrock-server-manager.readthedocs.io/en/latest/",
                                                        "title": "Docs Embed",
                                                        "height": "300px",
                                                    },
                                                }
                                            ],
                                        },
                                    ],
                                },
                                {
                                    "type": "Tab",
                                    "props": {"label": "Interactive", "id": 2},
                                    "children": [
                                        {
                                            "type": "Card",
                                            "props": {
                                                "title": "Interactive Components"
                                            },
                                            "children": [
                                                {
                                                    "type": "Accordion",
                                                    "props": {"title": "More Details"},
                                                    "children": [
                                                        {
                                                            "type": "Text",
                                                            "props": {
                                                                "content": "This content is hidden by default inside an accordion."
                                                            },
                                                        }
                                                    ],
                                                },
                                                {"type": "Divider"},
                                                {
                                                    "type": "Button",
                                                    "props": {
                                                        "label": "Open Modal",
                                                        "onClickAction": {
                                                            "type": "open_modal",
                                                            "modalId": "test_modal",
                                                        },
                                                    },
                                                },
                                            ],
                                        },
                                        {
                                            "type": "Modal",
                                            "props": {
                                                "id": "test_modal",
                                                "title": "Test Modal Dialog",
                                            },
                                            "children": [
                                                {
                                                    "type": "Text",
                                                    "props": {
                                                        "content": "This is a modal triggered by the button above."
                                                    },
                                                },
                                                {
                                                    "type": "Button",
                                                    "props": {
                                                        "label": "Close",
                                                        "onClickAction": {
                                                            "type": "close_modal"
                                                        },
                                                    },
                                                },
                                            ],
                                        },
                                    ],
                                },
                                {
                                    "type": "Tab",
                                    "props": {"label": "Monitoring", "id": 3},
                                    "children": [
                                        {
                                            "type": "Card",
                                            "props": {"title": "Charts & Monitoring"},
                                            "children": [
                                                {
                                                    "type": "Row",
                                                    "children": [
                                                        {
                                                            "type": "StatCard",
                                                            "props": {
                                                                "label": "CPU Usage",
                                                                "value": "45%",
                                                                "icon": "Activity",
                                                                "trend": "up",
                                                            },
                                                        },
                                                        {
                                                            "type": "StatCard",
                                                            "props": {
                                                                "label": "Memory",
                                                                "value": "1.2 GB",
                                                                "icon": "Save",
                                                                "trend": "neutral",
                                                            },
                                                        },
                                                    ],
                                                },
                                                {
                                                    "type": "Chart",
                                                    "props": {
                                                        "type": "area",
                                                        "height": 250,
                                                        "xAxis": "time",
                                                        "data": [
                                                            {
                                                                "time": "10:00",
                                                                "cpu": 30,
                                                                "memory": 20,
                                                            },
                                                            {
                                                                "time": "10:05",
                                                                "cpu": 45,
                                                                "memory": 25,
                                                            },
                                                            {
                                                                "time": "10:10",
                                                                "cpu": 35,
                                                                "memory": 30,
                                                            },
                                                            {
                                                                "time": "10:15",
                                                                "cpu": 50,
                                                                "memory": 35,
                                                            },
                                                            {
                                                                "time": "10:20",
                                                                "cpu": 40,
                                                                "memory": 40,
                                                            },
                                                        ],
                                                        "series": [
                                                            {
                                                                "dataKey": "cpu",
                                                                "color": "#8884d8",
                                                                "name": "CPU",
                                                            },
                                                            {
                                                                "dataKey": "memory",
                                                                "color": "#82ca9d",
                                                                "name": "Memory",
                                                            },
                                                        ],
                                                    },
                                                },
                                                {
                                                    "type": "Text",
                                                    "props": {
                                                        "content": "Log Stream",
                                                        "variant": "h3",
                                                    },
                                                },
                                                {
                                                    "type": "LogViewer",
                                                    "props": {
                                                        "height": 150,
                                                        "socketTopic": "server_log:{server}",
                                                        "lines": [],
                                                    },
                                                },
                                            ],
                                        }
                                    ],
                                },
                            ],
                        },
                    ],
                }
            )

        @self.router.post(
            "/api/dynamic_page_test/submit",
            tags=["Dynamic Page Test Plugin"],
            summary="Echo Submit",
        )
        async def submit_test_form(
            request: Request, current_user: Dict[str, Any] = Depends(get_admin_user)
        ):
            try:
                data = await request.json()
            except JSONDecodeError:
                data = {}

            return JSONResponse(
                content={
                    "status": "success",
                    "message": f"Received: {len(data)} fields",
                    "data": data,
                }
            )

    def on_unload(self, **kwargs):
        pass

    def get_fastapi_routers(self, **kwargs):
        return [self.router]
