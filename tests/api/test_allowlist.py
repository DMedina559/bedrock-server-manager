from unittest.mock import MagicMock

import pytest

from bedrock_server_manager.api.allowlist import (
    add_to_allowlist,
    get_allowlist,
    remove_from_allowlist,
)
from bedrock_server_manager.error import BSMError, MissingArgumentError


def test_add_to_allowlist_success(app_context, monkeypatch):
    """Test add_to_allowlist parses valid lists correctly."""
    mock_server = MagicMock()
    mock_server.add_to_allowlist.return_value = 1
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = add_to_allowlist(
        "test_server", [{"name": "player1", "xuid": "123"}], app_context
    )

    assert result["status"] == "success"
    assert result["added_count"] == 1


def test_add_to_allowlist_empty_server(app_context):
    """Test add_to_allowlist throws on missing server strings."""
    with pytest.raises(MissingArgumentError):
        add_to_allowlist("", [], app_context)


def test_add_to_allowlist_invalid_list(app_context):
    """Test add_to_allowlist returns an error if players data is not a list."""
    result = add_to_allowlist("test_server", "not_a_list", app_context)
    assert result["status"] == "error"
    assert "must be a list" in result["message"]


def test_get_allowlist_success(app_context, monkeypatch):
    """Test get_allowlist successfully retrieves from server."""
    mock_server = MagicMock()
    mock_server.get_allowlist.return_value = [{"name": "p1"}]
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = get_allowlist("test_server", app_context)

    assert result["status"] == "success"
    assert len(result["players"]) == 1


def test_get_allowlist_missing_server(app_context):
    """Test get_allowlist throws error when no server string is provided."""
    with pytest.raises(MissingArgumentError):
        get_allowlist("", app_context)


def test_get_allowlist_bsmerror(app_context, monkeypatch):
    """Test get_allowlist wraps BSMError in error dict."""

    def raise_err(*args):
        raise BSMError("File broken")

    monkeypatch.setattr(app_context, "get_server", raise_err)

    result = get_allowlist("test_server", app_context)
    assert result["status"] == "error"
    assert "File broken" in result["message"]


def test_remove_from_allowlist_success(app_context, monkeypatch):
    """Test remove_from_allowlist removes specific users and counts failures accurately."""
    mock_remove = MagicMock(
        side_effect=[True, False]
    )  # First player exists, second doesnt
    mock_server = MagicMock()
    mock_server.remove_from_allowlist = mock_remove
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = remove_from_allowlist("test_server", ["p1", "p2"], app_context)

    assert result["status"] == "success"
    assert "p1" in result["details"]["removed"]
    assert "p2" in result["details"]["not_found"]


def test_remove_from_allowlist_empty(app_context):
    """Test remove_from_allowlist shortcuts immediately when list is empty."""
    result = remove_from_allowlist("test_server", [], app_context)

    assert result["status"] == "success"
    assert len(result["details"]["removed"]) == 0


def test_remove_from_allowlist_missing_server(app_context):
    """Test remove_from_allowlist correctly validates server names."""
    with pytest.raises(MissingArgumentError):
        remove_from_allowlist("", ["p1"], app_context)
