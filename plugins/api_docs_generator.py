import datetime
import inspect
import json
import os
from typing import Any, Dict, List

from bedrock_server_manager import PluginBase, __version__, app_event
from bedrock_server_manager.events import server as status_events  # noqa: F401
from bedrock_server_manager.events.registry import builtin_events
from bedrock_server_manager.plugins.api_types import API_METHODS


class APIDocsGenerator(PluginBase):
    """
    A utility plugin that automatically generates Markdown documentation
    for all registered plugin API functions and application events.
    """

    version = "1.2.0"
    author = "dmedina559"
    description = "A utility plugin that automatically generates Markdown documentation for all registered plugin API functions and application events."
    name = "API Docs Generator"

    @app_event("on_load")
    async def plugin_loaded(self):
        self.logger.debug(
            "API Docs Generator plugin loaded. Will generate docs on manager startup."
        )

    @app_event("on_manager_startup")
    async def generate_docs(self, **kwargs: Any):
        """
        Triggered once when the application is fully started.
        This is the perfect time to inspect and document the API and events.
        """

        self.logger.info("Generating API and Event documentation...")

        try:
            # --- API Docs ---
            api_list = self.api.list_available_apis()
            api_markdown_content = self._format_api_markdown(api_list)
            backup_dir = (
                await self.api.settings.get_global_setting({"key": "paths.backups"})
            ).value
            if not isinstance(backup_dir, str):
                raise ValueError("Backup path must be a string")

            api_output_path = os.path.join(backup_dir, "PLUGIN_API_REFERENCE.md")

            def write_api_file():
                with open(api_output_path, "w", encoding="utf-8") as f:
                    f.write(api_markdown_content)

            write_api_file()
            self.logger.info(
                "Successfully generated API documentation at: %s", api_output_path
            )

            # --- Event Docs ---
            event_list = self._scan_codebase_for_events()
            event_markdown_content = self._format_event_markdown(event_list)
            event_output_path = os.path.join(backup_dir, "PLUGIN_EVENT_REFERENCE.md")

            def write_event_file():
                with open(event_output_path, "w", encoding="utf-8") as f:
                    f.write(event_markdown_content)

            write_event_file()
            self.logger.info(
                "Successfully generated Event documentation at: %s", event_output_path
            )

        except Exception as e:
            self.logger.error("Failed to generate documentation: %s", e, exc_info=True)

    def _scan_codebase_for_events(self) -> List[Dict[str, Any]]:
        """Document the live core event contracts, including non-API emitters."""
        events = []
        for definition in builtin_events.catalog().events:
            if definition.phase not in {"before", "after"}:
                continue
            parameters: dict[str, dict[str, Any]] = {}
            occurrences: dict[str, int] = {}
            models = builtin_events.payload_models(definition.name)
            for model in models:
                for name, field in model.model_fields.items():
                    annotation = field.annotation
                    type_name = (
                        annotation.__name__ if isinstance(annotation, type) else None
                    )
                    if type_name is None:
                        type_name = self._format_type_hint(annotation)
                    occurrences[name] = occurrences.get(name, 0) + 1
                    existing = parameters.get(name)
                    if existing and type_name not in existing["type_obj"].split(" | "):
                        type_name = existing["type_obj"] + " | " + type_name
                    parameters[name] = {"name": name, "type_obj": type_name}
            for name, parameter in parameters.items():
                if occurrences[name] < len(models):
                    parameter["optional"] = True
            events.append(
                {
                    "name": definition.name,
                    "type": definition.phase,
                    "cancellable": definition.phase == "before",
                    "docstring": definition.description,
                    "parameters": list(parameters.values()),
                    "identity_keys": definition.identity_keys,
                }
            )
        return events

    def _format_type_hint(self, annotation: Any) -> str:
        """
        Cleans up the string representation of a type hint for display.
        """
        if annotation == inspect.Parameter.empty:
            return "Any"

        # Get the string representation
        s = str(annotation)

        # Clean up common Python cruft
        s = s.replace("typing.", "")
        s = s.replace("<class '", "").replace("'>", "")

        return s

    def _format_api_markdown(self, api_list: list) -> str:
        """
        Takes the list of API details and converts it into a formatted Markdown string.
        """
        lines = [
            "# Available plugin APIs",
            "",
            f"> _This was auto-generated by the `api_docs_generator` plugin on {datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}._",
            f"> _Application Version: {__version__}_",
            "\n---",
            "This list contains all functions available to plugins via the `self.api` object.",
            "For an updated list of available APIs, please download and run the [api_docs_generator](https://github.com/DMedina559/bedrock-server-manager/blob/main/plugins/api_docs_generator.py) plugin.",
        ]

        sorted_api_list = sorted(
            api_list,
            key=lambda x: (x.get("domain", ""), x.get("name", "")),
        )
        for api_func in sorted_api_list:
            name = api_func.get("name", "Unknown Function")
            domain = api_func.get("domain", "")
            name = next(
                (
                    public
                    for public, registered in API_METHODS.get(domain, {}).items()
                    if registered == name
                ),
                name,
            )
            docstring = api_func.get("docstring", "No description.")
            params = api_func.get("parameters", [])
            is_async = api_func.get("is_async", True)

            param_parts = []
            for param in params:
                p_name = param["name"]
                if p_name == "app_context":
                    continue
                p_type = self._format_type_hint(param.get("type_obj"))
                p_default = param.get("default")

                if p_default == "REQUIRED":
                    param_parts.append(f"{p_name}: {p_type}")
                else:
                    default_str = f" = {repr(p_default)}"
                    param_parts.append(f"{p_name}: {p_type}{default_str}")

            full_name = f"{domain}.{name}" if domain else name
            signature_prefix = "await self.api." if is_async else "self.api."
            signature = f"{signature_prefix}{full_name}({', '.join(param_parts)})"

            lines.append(f"\n## `{full_name}`")
            lines.append(f"```python\n{signature}\n```")
            lines.append(
                f"- **Async (Requires await):** {'Yes' if is_async else 'No'}\n"
            )
            lines.append(f"- **Description:** {docstring}\n")

            if api_func.get("contract_version") == 2:
                request_model = api_func["request_model"]
                response_model = api_func["response_model"]
                request_schema = api_func["request_schema"]
                properties = request_schema.get("properties", {})
                required = request_schema.get("required", [])
                examples = {
                    field: properties[field]["examples"][0]
                    for field in required
                    if properties.get(field, {}).get("examples")
                }
                payload_line = (
                    f"payload = {examples!r}"
                    if len(examples) == len(required)
                    else "payload = {...}  # Supply required request fields below."
                )
                lines.append(f"- **Returns:** `{response_model}`\n")
                lines.append(
                    "Runtime context and plugin identity are injected by the bridge. "
                    "Failures raise application exceptions; plugin cancellation raises "
                    "`APICancelledError`.\n"
                )
                lines.append(
                    f"```python\nfrom bedrock_server_manager.api.models import {request_model}\n"
                    f"{payload_line}\n"
                    f"request = {request_model}(**payload)\n"
                    f"result = {signature_prefix}{full_name}(request)\n"
                    'data = result.model_dump(mode="json")\n```'
                )
                for label, schema_key in (
                    ("Request schema", "request_schema"),
                    ("Response schema", "response_schema"),
                    ("Transport error schema", "error_schema"),
                ):
                    schema = api_func.get(schema_key)
                    if schema:
                        lines.append(f"\n**{label}:**\n")
                        lines.append(
                            "```json\n"
                            + json.dumps(schema, indent=2, sort_keys=True)
                            + "\n```"
                        )

            filtered_params = [p for p in params if p["name"] != "app_context"]
            if filtered_params:
                lines.append("**Parameters:**\n")
                lines.append("| Name | Type | Default |")
                lines.append("|------|------|---------|")
                for param in filtered_params:
                    p_name = f"`{param['name']}`"
                    p_type = f"`{self._format_type_hint(param.get('type_obj'))}`"
                    p_default = f"`{repr(param.get('default'))}`"
                    if param.get("default") == "REQUIRED":
                        p_default = "`REQUIRED`"
                    lines.append(f"| {p_name} | {p_type} | {p_default} |")

            lines.append("\n---\n")

        return "\n".join(lines)

    def _format_event_markdown(self, event_list: list) -> str:
        """
        Takes the list of Event details and converts it into a formatted Markdown string.
        """
        lines = [
            "# Available plugin events",
            "",
            f"> _This was auto-generated by the `api_docs_generator` plugin on {datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}._",
            f"> _Application Version: {__version__}_",
            "\n---",
            "This list contains all core application events available to plugins.",
            'You can listen to these events using the `@app_event("event_name")` decorator.',
            "If an event is **Cancellable**, you can access `kwargs['event']` (which is a `CancellableEvent` object) and call `event.cancel(reason)` to halt the core operation.",
        ]

        for event in event_list:
            name = event.get("name", "Unknown Event")
            docstring = event.get("docstring", "No description.")
            params = event.get("parameters", [])
            is_cancellable = event.get("cancellable", False)
            identity_keys = event.get("identity_keys", [])

            lines.append(f"\n## `{name}`")
            lines.append(f"**Description:** {docstring}")
            lines.append(
                f"- **Cancellable:** {'Yes (`event.cancel()`)' if is_cancellable else 'No'}"
            )
            if identity_keys:
                lines.append(
                    f"- **Identity Keys (for re-entrancy):** `{', '.join(identity_keys)}`"
                )
            lines.append("")

            lines.append("### Listener Signature:")
            param_str = ", ".join(
                p["name"] + ("=None" if p.get("optional") else "") for p in params
            )
            if any(p.get("optional") for p in params):
                param_str = "*, " + param_str
            if is_cancellable:
                if param_str:
                    param_str += ", "
                param_str += "event"
            lines.append(
                f'```python\n@app_event("{name}")\nasync def some_function(self, {param_str}, **kwargs):\n    pass\n```'
            )

            if params or is_cancellable:
                lines.append("### Available `kwargs`:")
                lines.append("| Key Name | Type |")
                lines.append("|----------|------|")
                for param in params:
                    p_name = f"`{param['name']}`"
                    p_type = f"`{self._format_type_hint(param.get('type_obj'))}`"
                    lines.append(f"| {p_name} | {p_type} |")

                if is_cancellable:
                    lines.append("| `event` | `CancellableEvent` |")

                lines.append("| `_triggering_plugin` | `str` (core, or plugin name) |")

            lines.append("\n---\n")

        return "\n".join(lines)
