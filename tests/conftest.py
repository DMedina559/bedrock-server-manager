"""Shared integration fixtures; application I/O stays on the pytest event loop."""

pytest_plugins = [
    "bsm_test_utils.fixtures",
    "tests.fixtures.application",
    "tests.fixtures.websocket",
    "tests.fixtures.system_service",
]
