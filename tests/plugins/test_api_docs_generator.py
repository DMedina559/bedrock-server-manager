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
    assert "await self.api.server.start_server(request)" in markdown
    assert "StartServerResponse" in markdown
    assert '"additionalProperties": false' in markdown
    assert '"already_running"' in markdown
    assert "Transport error schema" in markdown
    assert "APICancelledError" in markdown
    events = {item["name"]: item for item in generator._scan_codebase_for_events()}
    assert [field["name"] for field in events["before_server_start"]["parameters"]] == [
        "server_name"
    ]
    assert events["after_server_start"]["parameters"][-1] == {
        "name": "result",
        "type_obj": "Dict[str, Any]",
    }
