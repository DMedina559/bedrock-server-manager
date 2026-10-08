import ast
import datetime
import inspect
import json
import os
from typing import Any, Dict, List

import bedrock_server_manager
from bedrock_server_manager import PluginBase, __version__, app_event
from bedrock_server_manager.api import models as api_models
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
        self.logger.info(
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
                f"Successfully generated API documentation at: {api_output_path}"
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
                f"Successfully generated Event documentation at: {event_output_path}"
            )

        except Exception as e:
            self.logger.error(f"Failed to generate documentation: {e}", exc_info=True)

    def _scan_codebase_for_events(self) -> List[Dict[str, Any]]:
        """
        Scans the bedrock_server_manager source code statically to find
        all @trigger_event usages and extract their documentation.
        """
        events_info = []

        # Get the root path of the bedrock_server_manager package
        base_dir = os.path.dirname(bedrock_server_manager.__file__)

        for root, _, files in os.walk(base_dir):
            for file in files:
                if file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            source = f.read()

                        # Quick string check to avoid parsing AST for files without the decorator
                        if "trigger_event" not in source:
                            continue

                        tree = ast.parse(source)

                        for node in ast.walk(tree):
                            if isinstance(
                                node, (ast.FunctionDef, ast.AsyncFunctionDef)
                            ):
                                for decorator in node.decorator_list:
                                    if (
                                        isinstance(decorator, ast.Call)
                                        and isinstance(decorator.func, ast.Name)
                                        and decorator.func.id == "trigger_event"
                                    ):
                                        before_name = None
                                        after_name = None
                                        identity_keys = []

                                        for kw in decorator.keywords:
                                            if kw.arg == "before" and isinstance(
                                                kw.value, ast.Constant
                                            ):
                                                before_name = kw.value.value
                                            elif kw.arg == "after" and isinstance(
                                                kw.value, ast.Constant
                                            ):
                                                after_name = kw.value.value
                                            elif (
                                                kw.arg == "identity_keys"
                                                and isinstance(
                                                    kw.value, (ast.Tuple, ast.List)
                                                )
                                            ):
                                                identity_keys = [
                                                    elt.value
                                                    for elt in kw.value.elts
                                                    if isinstance(elt, ast.Constant)
                                                ]

                                        docstring = (
                                            ast.get_docstring(node) or "No description."
                                        )
                                        first_line_doc = docstring.split("\n")[0]

                                        # Extract function parameters from AST
                                        params: list[dict[str, Any]] = []

                                        # Handle positional args
                                        for arg in (
                                            node.args.args + node.args.kwonlyargs
                                        ):
                                            p_name = arg.arg
                                            # Simple heuristic: if it's 'self' or 'cls', skip it.
                                            # We also hide 'app_context' since plugins don't usually need it directly from kwargs.
                                            if p_name in ("self", "cls", "app_context"):
                                                continue

                                            if p_name == "request" and isinstance(
                                                arg.annotation, ast.Name
                                            ):
                                                model = getattr(
                                                    api_models, arg.annotation.id, None
                                                )
                                                if model is not None:
                                                    params.append(
                                                        {
                                                            "name": "request",
                                                            "type_obj": arg.annotation.id,
                                                        }
                                                    )
                                                    params.extend(
                                                        {
                                                            "name": (
                                                                "plugin_name"
                                                                if field_name
                                                                == "target_plugin_name"
                                                                else field_name
                                                            ),
                                                            "type_obj": self._format_type_hint(
                                                                field.annotation
                                                            ),
                                                        }
                                                        for field_name, field in model.model_fields.items()
                                                    )
                                                    continue

                                            # Determine type if annotated
                                            p_type = "Any"
                                            if arg.annotation:
                                                p_type = ast.unparse(arg.annotation)

                                            params.append(
                                                {
                                                    "name": p_name,
                                                    "type_obj": p_type,
                                                }
                                            )

                                        # Note: Default values are trickier via static AST and we only need names/types for the docs.

                                        if before_name:
                                            events_info.append(
                                                {
                                                    "name": before_name,
                                                    "type": "before",
                                                    "cancellable": True,
                                                    "docstring": f"Triggered before '{node.name}'. {first_line_doc}",
                                                    "parameters": params,
                                                    "identity_keys": identity_keys,
                                                }
                                            )

                                        if after_name:
                                            after_params = params.copy()
                                            return_type = "Any"
                                            if node.returns:
                                                return_type = ast.unparse(node.returns)
                                                if isinstance(
                                                    node.returns, ast.Name
                                                ) and hasattr(
                                                    api_models, node.returns.id
                                                ):
                                                    return_type = node.returns.id

                                            after_params.append(
                                                {
                                                    "name": "result",
                                                    "type_obj": return_type,
                                                }
                                            )
                                            events_info.append(
                                                {
                                                    "name": after_name,
                                                    "type": "after",
                                                    "cancellable": False,
                                                    "docstring": f"Triggered after '{node.name}'. {first_line_doc}",
                                                    "parameters": after_params,
                                                    "identity_keys": identity_keys,
                                                }
                                            )
                    except Exception as e:
                        self.logger.debug(f"Could not parse source for {filepath}: {e}")

        # Deduplicate and sort
        unique_events = {}
        for event in events_info:
            unique_events[event["name"]] = event

        return sorted(list(unique_events.values()), key=lambda x: x["name"])

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
            param_str = ", ".join([f"{p['name']}" for p in params])
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
