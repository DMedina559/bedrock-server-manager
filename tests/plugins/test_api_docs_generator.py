"""Generated plugin docs reflect live request/response schema contracts."""

import importlib.util
from pathlib import Path

from bedrock_server_manager.plugins.api_bridge import create_app_api


def test_generated_docs_include_lifecycle_contract_and_usable_example():
    path = Path(__file__).parents[2] / "plugins" / "api_docs_generator.py"
    spec = importlib.util.spec_from_file_location("api_docs_generator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    generator = module.APIDocsGenerator.__new__(module.APIDocsGenerator)
    api = create_app_api("documentation", None)
    contracts = [
        item for item in api.list_available_apis() if item["name"] == "start_server"
    ]
    markdown = generator._format_api_markdown(contracts)
    assert (
        "from bedrock_server_manager.api.models import StartServerRequest" in markdown
    )
    assert "payload = {'server_name': 'example'}" in markdown
    assert "await self.api.server.start(request)" in markdown
    assert "StartServerResponse" in markdown
    assert '"additionalProperties": false' in markdown
    assert '"already_running"' in markdown
    assert "Transport error schema" in markdown
    assert "APICancelledError" in markdown
    events = {item["name"]: item for item in generator._scan_codebase_for_events()}
    assert [field["name"] for field in events["before_server_start"]["parameters"]] == [
        "request",
        "server_name",
    ]
    assert events["after_server_start"]["parameters"][-1] == {
        "name": "result",
        "type_obj": "StartServerResponse",
    }

    assert "before_server_status_change" in events
    assert events["before_server_status_change"]["identity_keys"] == (
        "server_name",
        "status",
    )
    assert (
        events["after_server_status_change"]["parameters"][-1]["type_obj"]
        == "StatusResult"
    )

    allowlist = events["before_allowlist_change"]
    fields = {field["name"]: field for field in allowlist["parameters"]}
    assert fields["new_players_data"]["optional"]
    assert fields["player_names"]["optional"]
    assert "AddToAllowlistRequest" in fields["request"]["type_obj"]
    assert "RemoveFromAllowlistRequest" in fields["request"]["type_obj"]
    assert "new_players_data=None" in generator._format_event_markdown([allowlist])


async def test_ping_pong_examples_use_typed_owned_events(plugin_factory, caplog):
    import logging

    from bedrock_server_manager.api.models import StartServerResponse

    root = Path(__file__).parents[2] / "plugins"
    ping = await plugin_factory("ping_plugin", (root / "ping_plugin.py").read_text())
    await plugin_factory("pong_plugin", (root / "pong_plugin.py").read_text())
    with caplog.at_level(logging.INFO):
        await ping.send_ping_event(
            "example",
            StartServerResponse(
                server_name="example",
                status="success",
                outcome="started",
                message="Started",
            ),
        )
    assert "Received ping for example" in caplog.text


def test_type_labels_ignore_validation_repr_and_normalize_union_syntax():
    from typing import Annotated, Optional, Union

    from pydantic import Field

    spec = importlib.util.spec_from_file_location(
        "api_docs_generator",
        Path(__file__).parents[2] / "plugins/api_docs_generator.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    generator = module.APIDocsGenerator.__new__(module.APIDocsGenerator)
    for metadata in (Field(min_length=1), Field(min_length=2, strict=True)):
        assert (
            generator._format_type_hint(list[Annotated[str, metadata]]) == "list[str]"
        )
    for annotation in (Optional[str], str | None):
        assert generator._format_type_hint(annotation) == "str | None"
    assert generator._format_type_hint(Union[int, str]) == generator._format_type_hint(
        int | str
    )
