from unittest.mock import patch

import pytest

from bedrock_server_manager.error import SystemError
from bedrock_server_manager.utils.get_utils import (
    _get_splash_text,
    get_operating_system_type,
)


def test_get_splash_text_from_dict():
    """Test get_splash_text successfully flattens and retrieves from a dictionary."""
    with patch(
        "bedrock_server_manager.utils.get_utils.SPLASH_TEXTS",
        {"test_cat": ["splash1", "splash2"]},
    ):
        splash = _get_splash_text()
        assert splash in ["splash1", "splash2"]


def test_get_splash_text_from_list():
    """Test get_splash_text directly retrieves from a list."""
    with patch(
        "bedrock_server_manager.utils.get_utils.SPLASH_TEXTS",
        ["splash_list_1", "splash_list_2"],
    ):
        splash = _get_splash_text()
        assert splash in ["splash_list_1", "splash_list_2"]


def test_get_splash_text_empty_list():
    """Test get_splash_text falls back correctly when receiving an empty list."""
    with patch("bedrock_server_manager.utils.get_utils.SPLASH_TEXTS", []):
        splash = _get_splash_text()
        assert splash == "Amazing Error Handling!"


def test_get_splash_text_none():
    """Test get_splash_text falls back correctly when None is passed."""
    with patch("bedrock_server_manager.utils.get_utils.SPLASH_TEXTS", None):
        splash = _get_splash_text()
        assert splash == "Amazing Error Handling!"


def test_get_operating_system_type_linux():
    """Test get_operating_system_type returns Linux accurately."""
    with patch("platform.system", return_value="Linux"):
        os_type = get_operating_system_type()
        assert os_type == "Linux"


def test_get_operating_system_type_windows():
    """Test get_operating_system_type returns Windows accurately."""
    with patch("platform.system", return_value="Windows"):
        os_type = get_operating_system_type()
        assert os_type == "Windows"


def test_get_operating_system_type_error():
    """Test get_operating_system_type raises a SystemError on empty responses."""
    with patch("platform.system", return_value=""):
        with pytest.raises(SystemError) as exc_info:
            get_operating_system_type()
        assert "Could not determine operating system type" in str(exc_info.value)


def test_get_operating_system_type_exception():
    """Test get_operating_system_type raises a SystemError catching unexpected exceptions."""
    with patch("platform.system", side_effect=Exception("Platform failure")):
        with pytest.raises(SystemError) as exc_info:
            get_operating_system_type()
        assert "Failed to get OS type" in str(exc_info.value)
