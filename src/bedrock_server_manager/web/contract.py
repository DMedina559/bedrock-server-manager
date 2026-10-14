"""Export and compare the core HTTP contract without starting application services.

Clients use this module from the backend checkout they are targeting. Contract
exports omit installed plugins and normalize only release metadata and Python's
standard HTTP 422 reason phrase. Runtime OpenAPI retains the installed version.
"""

from __future__ import annotations

import argparse
import copy
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from ..context import AppContext
from .app import create_web_app

HTTP_METHODS = frozenset(
    {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
)


def normalize_contract(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a stable copy while preserving all API structure and custom text."""
    result = copy.deepcopy(schema)
    result.setdefault("info", {})["version"] = "contract"
    for item in result.get("paths", {}).values():
        for method, operation in item.items():
            if method not in HTTP_METHODS:
                continue
            response = operation.get("responses", {}).get("422", {})
            if response.get("description") in {
                "Unprocessable Entity",
                "Unprocessable Content",
            }:
                response["description"] = "Unprocessable Entity"
    return result


def export_contract() -> dict[str, Any]:
    """Build registered core routers with no database, plugins, or lifespan."""
    with tempfile.TemporaryDirectory(prefix="bsm-contract-") as directory:
        context = SimpleNamespace(
            settings={"paths.themes": directory},
            get_pre_app_config=lambda _key, default: default,
            plugin_manager=SimpleNamespace(bind_web_app=lambda _app: None),
        )
        app = create_web_app(cast(AppContext, context))
        schema = normalize_contract(app.openapi())
    operation_ids: set[str] = set()
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            if method not in HTTP_METHODS:
                continue
            identifier = operation.get("operationId")
            if not identifier or identifier in operation_ids:
                raise ValueError(f"Missing or duplicate operationId: {method} {path}")
            operation_ids.add(identifier)
    return schema


def contract_changes(
    expected: dict[str, Any], actual: dict[str, Any]
) -> dict[str, list[str]]:
    """Describe drift, including response models, shared parameters and metadata."""

    def operations(schema: dict[str, Any]) -> dict[str, Any]:
        return {
            operation["operationId"]: {"path": path, "method": method, **operation}
            for path, item in schema.get("paths", {}).items()
            for method, operation in item.items()
            if method in HTTP_METHODS
        }

    old, new = operations(expected), operations(actual)
    old_models = expected.get("components", {}).get("schemas", {})
    new_models = actual.get("components", {}).get("schemas", {})
    return {
        "Added operations": sorted(new.keys() - old.keys()),
        "Removed operations": sorted(old.keys() - new.keys()),
        "Changed operations": sorted(
            key for key in old.keys() & new.keys() if old[key] != new[key]
        ),
        "Changed models": sorted(
            key
            for key in old_models.keys() | new_models.keys()
            if old_models.get(key) != new_models.get(key)
        ),
        "Changed sections": sorted(
            key
            for key in expected.keys() | actual.keys()
            if expected.get(key) != actual.get(key)
        ),
    }


def main() -> None:
    """Write canonical JSON or fail if a bundled document differs from the backend."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    if args.output is None and args.check is None:
        parser.error("provide --output and/or --check")
    actual = export_contract()
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(actual, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if args.check is not None:
        expected = json.loads(args.check.read_text(encoding="utf-8"))
        if expected != actual:
            for label, changes in contract_changes(expected, actual).items():
                print(f"{label}: {changes}")
            raise SystemExit(
                "Backend contract drift. Regenerate and review the schema and client."
            )
        print("Backend HTTP contract matches the bundled schema.")


if __name__ == "__main__":
    main()
