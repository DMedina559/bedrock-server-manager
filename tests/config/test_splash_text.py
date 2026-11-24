from unittest.mock import patch

from bedrock_server_manager.config.splash_text import _get_splash_text, get_splash_text


def test_get_splash_text_from_dict():
    """Test get_splash_text successfully flattens and retrieves from a dictionary."""
    with patch(
        "bedrock_server_manager.config.splash_text.SPLASH_TEXTS",
        {"test_cat": ["splash1", "splash2"]},
    ):
        splash = get_splash_text()
        assert splash in ["splash1", "splash2"]


def test_get_splash_text_from_list():
    """Test get_splash_text directly retrieves from a list."""
    with patch(
        "bedrock_server_manager.config.splash_text.SPLASH_TEXTS",
        ["splash_list_1", "splash_list_2"],
    ):
        splash = _get_splash_text()
        assert splash in ["splash_list_1", "splash_list_2"]


def test_get_splash_text_empty_list():
    """Test get_splash_text falls back correctly when receiving an empty list."""
    with patch("bedrock_server_manager.config.splash_text.SPLASH_TEXTS", []):
        splash = get_splash_text()
        assert splash == "Amazing Error Handling!"


def test_get_splash_text_none():
    """Test get_splash_text falls back correctly when None is passed."""
    with patch("bedrock_server_manager.config.splash_text.SPLASH_TEXTS", None):
        splash = get_splash_text()
        assert splash == "Amazing Error Handling!"
