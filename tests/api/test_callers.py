"""Prevent legacy argument dispatch from bypassing typed contracts."""

import runpy
from pathlib import Path

import pytest


def checker():
    return runpy.run_path(
        str(Path(__file__).resolve().parents[2] / "scripts/check_api_callers.py")
    )


def test_production_api_callers_match_contracts():
    checked, errors = checker()["check_repository"]()
    assert checked > 100
    assert errors == []


@pytest.mark.parametrize(
    "call",
    [
        "await api.backup_world(server_name='example', app_context=context)",
        "target = api.backup_world\nawait manager.run_task(target, server_name='example', app_context=context)",
        "await manager.run_task(api.backup_world, **legacy_kwargs)",
    ],
)
def test_checker_detects_legacy_and_unverifiable_dispatch(call):
    audit = checker()
    source = "from bedrock_server_manager.api import backup_restore as api\n" + call
    checked, errors = audit["check_source"](
        source, "bedrock_server_manager.web.routers", audit["contracts"]()
    )
    assert checked == 1
    assert errors
