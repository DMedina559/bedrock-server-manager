# Custom Events & Advanced Hooks

## Custom Plugin Events (Inter-Plugin Communication)

Plugins can define, send, and listen to their own custom events for complex interactions.

*   **Sending Events:** Use `await self.api.send_event("myplugin:custom_action", arg1, kwarg1="value")`.
*   **Listening for Events:** Decorate an async method with `@app_event("some:event")`.
*   **Callback Arguments:** Your callback function will receive any `*args` and `**kwargs` from the sender.

### Example: "I'm Home" Automation (Triggered via HTTP API)

An external system can trigger a plugin to start a server by sending a `POST` request to `/api/plugins/trigger_event` with a JSON body. The corresponding plugin would listen for this event:

```python
# home_automation_starter_plugin.py
from bedrock_server_manager import PluginBase, app_event

TARGET_SERVER_NAME = "main_survival"

class HomeAutomationStarterPlugin(PluginBase):
    version = "4.0.0"

    @app_event("on_load")
    async def plugin_loaded(self, **kwargs):
        self.logger.info(f"Listening for 'automation:user_arrived_home' to start '{TARGET_SERVER_NAME}'.")

    @app_event("automation:user_arrived_home")
    async def handle_user_arrival(self, **kwargs):
        user_id = kwargs.get('user_id', 'UnknownUser')
        self.logger.info(f"Received arrival event for user '{user_id}'.")

        status = await self.api.get_server_running_status(server_name=TARGET_SERVER_NAME)
        if status.get("is_running"):
             self.logger.info(f"Server '{TARGET_SERVER_NAME}' is already running.")
             return

        await self.api.start_server(server_name=TARGET_SERVER_NAME)
```

### Advanced Event Hooks (Cancellation & Interception)

You can use `before_*` hooks to intercept actions. If an event is marked as **Cancellable**, the event payload will include a `CancellableEvent` object named `event` (or accessible via `kwargs['event']`). You can call `event.cancel(reason)` to completely halt the core application operation!

```python
from bedrock_server_manager import app_event, PluginBase

class BackupBeforeStartPlugin(PluginBase):
    version = "4.0.0"

    @app_event("before_server_start")
    async def handle_before_server_start(self, **kwargs):
        """Runs automatically before a server is started."""
        server_name = kwargs.get("server_name")
        event = kwargs.get("event")
        self.logger.info(f"Intercepted start request for {server_name}. Running quick backup...")

        result = await self.api.backup_world(server_name=server_name)

        if result.get("status") == "success":
            self.logger.info("Backup completed. Allowing server to start.")
        else:
            self.logger.error("Backup failed! Halting server start.")
            if event:
                event.cancel("Pre-start backup failed, aborting start for safety.")
```

### Catch-All Event Listeners (Wildcard)

You can listen to *every* event dispatched by the Plugin Manager by using the wildcard `*` symbol in your `@app_event` decorator. This is useful for auditing, debugging, or logging tools.

```python
from bedrock_server_manager import app_event, PluginBase

class AuditPlugin(PluginBase):
    version = "4.0.0"

    @app_event("*")
    async def on_any_event(self, event_name: str, **kwargs):
        # Note: The wildcard listener receives the original 'event_name' as its first positional argument.
        self.logger.info(f"System fired event: {event_name} with args: {kwargs}")
```
