"""Canonical exports must remain stable without hiding API changes."""

import copy

import pytest

from bedrock_server_manager.web.contract import (
    contract_changes,
    export_contract,
    normalize_contract,
)


@pytest.mark.parametrize("phrase", ["Unprocessable Entity", "Unprocessable Content"])
def test_export_normalizes_python_http_status_descriptions(phrase):
    schema = {
        "paths": {
            "/test": {
                "parameters": [],
                "get": {
                    "responses": {
                        "422": {"description": phrase},
                        "200": {"description": "OK"},
                    }
                },
                "post": {
                    "responses": {"422": {"description": "Custom validation message"}}
                },
            }
        }
    }
    normalized = normalize_contract(schema)
    assert (
        normalized["paths"]["/test"]["get"]["responses"]["422"]["description"]
        == "Unprocessable Entity"
    )
    assert (
        normalized["paths"]["/test"]["get"]["responses"]["200"]["description"] == "OK"
    )
    assert (
        normalized["paths"]["/test"]["post"]["responses"]["422"]["description"]
        == "Custom validation message"
    )


def test_normalization_preserves_constraints_and_original_document():
    schema = {
        "info": {"version": "4.0.0b5"},
        "components": {
            "schemas": {"Config": {"type": "object", "additionalProperties": False}}
        },
    }
    original = copy.deepcopy(schema)
    actual = normalize_contract(schema)
    assert schema == original
    assert actual["info"]["version"] == "contract"
    assert actual["components"] == schema["components"]


def test_export_matches_registered_core_routes_without_loading_runtime(app_context):
    from bedrock_server_manager.web.app import create_web_app

    actual = export_contract()
    expected = normalize_contract(create_web_app(app_context).openapi())
    assert actual == expected
    assert (
        actual["paths"]["/api/server/{server_name}/properties/raw"]["get"][
            "operationId"
        ]
        == "get_raw_properties"
    )


def test_diff_reports_route_moves_and_model_constraint_changes():
    expected = {
        "paths": {"/old": {"get": {"operationId": "read"}}},
        "components": {"schemas": {"Config": {"type": "object"}}},
    }
    actual = {
        "paths": {"/new": {"get": {"operationId": "read"}}},
        "components": {
            "schemas": {"Config": {"type": "object", "additionalProperties": False}}
        },
    }
    changes = contract_changes(expected, actual)
    assert changes["Changed operations"] == ["read"]
    assert changes["Changed models"] == ["Config"]
