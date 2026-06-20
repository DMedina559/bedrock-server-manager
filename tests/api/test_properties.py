from unittest.mock import patch

from bedrock_server_manager.api.properties import (
    get_properties,
    set_properties,
    validate_property_value,
)


class TestProperties:
    def test_get_properties(self, app_context):
        result = get_properties("test_server", app_context=app_context)
        assert result["status"] == "success"
        assert result["properties"]["level-name"] == "world"

    def test_validate_property_value(self):
        assert (
            validate_property_value("level-name", "valid-world")["status"] == "success"
        )
        assert (
            validate_property_value("level-name", "invalid world!")["status"] == "error"
        )

    @patch("bedrock_server_manager.api.properties.server_lifecycle_manager")
    def test_set_properties(self, mock_lifecycle, app_context):
        server = app_context.get_server("test_server")
        result = set_properties(
            "test_server", {"level-name": "new-world"}, app_context=app_context
        )
        assert result["status"] == "success"
        mock_lifecycle.assert_called_once()

        # Check the server.properties file
        properties = server.get_server_properties()
        assert properties["level-name"] == "new-world"
