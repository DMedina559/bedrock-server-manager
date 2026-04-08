# Native JSON UI for Plugins

Bedrock Server Manager allows plugins to define native UI pages using a simple JSON schema. This eliminates the need for plugin developers to write frontend code (React, HTML, CSS) while still providing a rich, interactive user interface that matches the application's look and feel.

## How it Works

Instead of serving HTML or Jinja2 templates, your plugin defines a FastAPI route that returns a JSON response. This route is tagged with `plugin-ui-native`. The frontend detects this tag and renders the JSON using a dynamic component renderer.

### Global Server Context

The Web UI features a global server selector in the sidebar. When a user navigates to your plugin's Native UI page, the frontend automatically appends the currently selected server name to the URL as a query parameter (e.g., `?server=survival_server`).

Your FastAPI route should accept this `server` query parameter to dynamically fetch and display data for the chosen server. If the user changes the server in the dropdown, your UI route will be re-fetched with the new `server` parameter.

**Example:**
```python
@self.router.get("/my_plugin/ui", response_class=JSONResponse, tags=["plugin-ui-native"])
async def get_ui(server: str = "default_server"): # Accept the server query param
    # Fetch data specific to the selected server using the Core API
    status = self.api.get_server_running_status(server)
    is_running = status.get("running", False)

    return JSONResponse(content={
        "type": "Card",
        "props": {"title": f"Status for {server}"},
        "children": [
            {
                "type": "Badge",
                "props": {
                    "content": "Online" if is_running else "Offline",
                    "variant": "success" if is_running else "danger"
                }
            }
        ]
    })
```

### Basic Example

Here is a minimal example of a plugin that adds a native UI page:

```python
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from bedrock_server_manager import PluginBase

class MyPlugin(PluginBase):
    def on_load(self, **kwargs):
        self.router = APIRouter(tags=["My Plugin"])

        @self.router.get(
            "/my_plugin/ui",
            response_class=JSONResponse,
            name="My Plugin UI",
            tags=["plugin-ui-native"]  # <--- This tag enables the Native UI renderer
        )
        async def get_ui(request: Request):
            return JSONResponse(content={
                "type": "Container",
                "children": [
                    {
                        "type": "Text",
                        "props": {"content": "Hello from Native UI!", "variant": "h1"}
                    },
                    {
                        "type": "Card",
                        "props": {"title": "My Card"},
                        "children": [
                            {"type": "Text", "props": {"content": "This is content inside a card."}}
                        ]
                    }
                ]
            })

    def get_fastapi_routers(self, **kwargs):
        return [self.router]
```

## Available Components

The JSON schema supports a wide range of components. Each component is an object with `type`, `props`, and optional `children`.

### Layout
*   **Container**: Main wrapper.
*   **Card**: Boxed container with an optional `title`.
*   **Row**: Horizontal layout.
*   **Column**: Vertical layout.
*   **Divider**: Horizontal line separator.

### Typography
*   **Text**: Renders text.
    *   `content`: The text to display.
    *   `variant`: `h1`, `h2`, `h3`, or `body`.

### Basic Inputs
*   **Input**: Text input.
*   **Select**: Dropdown menu.
*   **Switch**: Toggle switch.
*   **Checkbox**: Checkbox input.
*   **Button**: Clickable button.
    *   `label`: Text on the button.
    *   `icon`: Name of the Lucide icon (e.g., "Save", "Play").
    *   `variant`: `primary`, `secondary`, `danger`.
    *   `onClickAction`: Action definition (see Actions below).
*   **FileUpload**: File selection input.

### Display & Media
*   **Badge**: Status label.
    *   `content`: Text.
    *   `variant`: `primary`, `secondary`, `success`, `danger`, `warning`.
*   **CodeBlock**: Displays code or logs with a copy button.
    *   `content`: The code/text.
    *   `title`: Optional header.
*   **Image**: Displays an image.
*   **Link**: External or internal link.
*   **iframe**: Embeds external content.

### Interactive
*   **Accordion**: Collapsible section.
*   **Modal**: Dialog popup.
    *   `id`: Unique ID to control visibility.
    *   `title`: Header text.
    *   `children`: Content inside the modal.

### Data & Monitoring
*   **Table**: Displays tabular data.
*   **StatCard**: Dashboard metric card.
    *   `label`: Title of the metric.
    *   `value`: The value to display.
    *   `icon`: Icon name.
    *   `trend`: `up`, `down`, or `neutral`.
*   **StatusIndicator**: Dot with status text.
    *   `status`: `running` (green), `stopped` (red), `warning` (orange).
*   **LogViewer**: Scrolling log display.
    *   `lines`: Array of log strings.
    *   `height`: Height in pixels (default 200).
*   **Chart**: Data visualization (Area, Line, Bar).
    *   `type`: `area`, `line`, `bar`.
    *   `data`: Array of data objects.
    *   `xAxis`: Key for the X-axis (e.g., "time").
    *   `series`: Array of objects defining lines/bars (`dataKey`, `color`, `name`).

## Actions

Components like `Button` can trigger actions via the `onClickAction` prop.

### API Call
Sends a POST request to a backend endpoint.
```json
{
    "type": "api_call",
    "endpoint": "/api/my_plugin/submit",
    "includeFormState": true,  // Sends current input values
    "refresh": true,           // Refreshes the UI after success
    "closeModal": true         // Closes any open modal
}
```

### Navigate
Navigates to another URL or updates query parameters.
```json
{
    "type": "navigate",
    "url": "/another/page"
}
```

### Modal Control
Opens or closes a modal by ID.
```json
{
    "type": "open_modal",
    "modalId": "my_modal_id"
}
```
```json
{
    "type": "close_modal"
}
```

## Real-time Updates (WebSockets)

You can subscribe to WebSocket topics to update components like Charts, StatCards, and LogViewers in real-time.

1.  **Define Subscriptions**: Add `websocketSubscriptions` to the root of your JSON response.
    ```json
    {
        "websocketSubscriptions": ["my_plugin:stats", "server_log:{server}"],
        "type": "Container"
    }
    ```
    *   `{server}` is automatically replaced with the currently selected server name.

2.  **Bind Components**: Pass `socketTopic` to components.
    *   **Chart**: Appends new data points from the socket message to the chart history.
    *   **LogViewer**: Appends new log lines.
    *   **StatCard**: Updates the value. Use `dataKey` to specify which field in the socket message to display (e.g., `process_info.cpu_percent`).

    ```json
    {
        "type": "StatCard",
        "props": {
            "label": "CPU",
            "socketTopic": "my_plugin:stats",
            "dataKey": "cpu_usage"
        }
    }
    ```

## Icons

The system uses [Lucide React](https://lucide.dev/icons) icons. You can use any valid Lucide icon name in props like `icon`. Common icons include: `Activity`, `AlertCircle`, `CheckCircle2`, `Info`, `Terminal`, `Save`, `Trash2`, `Plus`, `X`, `Upload`, `Download`, `Play`, `Square`, `RotateCcw`.

## Comprehensive Examples

### Form and API Submission

This example creates a simple form inside a Card and a Save button that submits the form data to an API endpoint. The `includeFormState: true` prop ensures all input values on the page are sent in the POST request body.

```json
{
  "type": "Container",
  "children": [
    {
      "type": "Card",
      "props": {
        "title": "Plugin Settings"
      },
      "children": [
        {
          "type": "Input",
          "props": {
            "name": "api_key",
            "label": "External API Key",
            "type": "password",
            "placeholder": "Enter your key..."
          }
        },
        {
          "type": "Switch",
          "props": {
            "name": "enable_feature_x",
            "label": "Enable Feature X",
            "defaultChecked": true
          }
        },
        {
          "type": "Button",
          "props": {
            "label": "Save Configuration",
            "icon": "Save",
            "variant": "primary",
            "onClickAction": {
              "type": "api_call",
              "endpoint": "/api/plugins/my_plugin/save_settings",
              "method": "POST",
              "includeFormState": true,
              "refresh": true
            }
          }
        }
      ]
    }
  ]
}
```

### Table View

Displaying data in a table with customizable columns and rows.

```json
{
  "type": "Card",
  "props": {
    "title": "Recent Actions"
  },
  "children": [
    {
      "type": "Table",
      "props": {
        "columns": [
          { "header": "User", "accessor": "user" },
          { "header": "Action", "accessor": "action" },
          { "header": "Timestamp", "accessor": "timestamp" },
          { "header": "Status", "accessor": "status" }
        ],
        "data": [
          { "user": "admin", "action": "Server Start", "timestamp": "2023-10-27 10:00", "status": "Success" },
          { "user": "mod_1", "action": "Config Update", "timestamp": "2023-10-27 11:30", "status": "Success" },
          { "user": "admin", "action": "Backup Run", "timestamp": "2023-10-27 12:00", "status": "Failed" }
        ]
      }
    }
  ]
}
```

### Real-Time Monitoring Dashboard

A combination of layout components (`Row`, `Column`) and real-time components (`StatCard`, `LogViewer`) bound to WebSocket topics. Notice the root `websocketSubscriptions` array.

```json
{
  "websocketSubscriptions": [
    "server_process_stats:{server}",
    "server_log:{server}"
  ],
  "type": "Container",
  "children": [
    {
      "type": "Text",
      "props": {
        "content": "Live Server Telemetry",
        "variant": "h2"
      }
    },
    {
      "type": "Row",
      "children": [
        {
          "type": "Column",
          "children": [
            {
              "type": "StatCard",
              "props": {
                "label": "CPU Usage",
                "value": "0%",
                "icon": "Cpu",
                "socketTopic": "server_process_stats:{server}",
                "dataKey": "cpu_percent_str",
                "trend": "neutral"
              }
            }
          ]
        },
        {
          "type": "Column",
          "children": [
            {
              "type": "StatCard",
              "props": {
                "label": "Memory",
                "value": "0 MB",
                "icon": "MemoryStick",
                "socketTopic": "server_process_stats:{server}",
                "dataKey": "memory_str"
              }
            }
          ]
        }
      ]
    },
    {
      "type": "Card",
      "props": {
        "title": "Live Console"
      },
      "children": [
        {
          "type": "LogViewer",
          "props": {
            "socketTopic": "server_log:{server}",
            "lines": ["--- Waiting for logs ---"],
            "height": 300
          }
        }
      ]
    }
  ]
}
```
