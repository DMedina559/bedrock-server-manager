from unittest.mock import patch

import pytest

from bedrock_server_manager.error import SystemError
from bedrock_server_manager.utils.get_utils import (
    _get_splash_text,
    get_operating_system_type,
)


class TestGetSplashText:
    @patch(
        "bedrock_server_manager.utils.get_utils.SPLASH_TEXTS",
        {"test": ["splash1", "splash2"]},
    )
    def test_get_splash_text_from_dict(self):
        """Tests that a splash text is correctly retrieved from a dictionary."""
        splash = _get_splash_text()
        assert splash in ["splash1", "splash2"]

    @patch(
        "bedrock_server_manager.utils.get_utils.SPLASH_TEXTS", ["splash1", "splash2"]
    )
    def test_get_splash_text_from_list(self):
        """Tests that a splash text is correctly retrieved from a list."""
        splash = _get_splash_text()
        assert splash in ["splash1", "splash2"]

    @patch("bedrock_server_manager.utils.get_utils.SPLASH_TEXTS", [])
    def test_get_splash_text_empty_list(self):
        """Tests that the fallback splash text is returned for an empty list."""
        splash = _get_splash_text()
        assert splash == "Amazing Error Handling!"

    @patch("bedrock_server_manager.utils.get_utils.SPLASH_TEXTS", None)
    def test_get_splash_text_not_defined(self):
        """Tests that the fallback splash text is returned when SPLASH_TEXTS is not defined."""
        splash = _get_splash_text()
        assert splash == "Amazing Error Handling!"


class TestGetOperatingSystemType:
    @patch("platform.system", return_value="Linux")
    def test_get_operating_system_type_linux(self, mock_system):
        """Tests that the correct OS type is returned for Linux."""
        assert get_operating_system_type() == "Linux"

    @patch("platform.system", return_value="Windows")
    def test_get_operating_system_type_windows(self, mock_system):
        """Tests that the correct OS type is returned for Windows."""
        assert get_operating_system_type() == "Windows"

    @patch("platform.system", return_value="")
    def test_get_operating_system_type_error(self, mock_system):
        """Tests that a SystemError is raised if the OS type cannot be determined."""
        with pytest.raises(SystemError):
            get_operating_system_type()
