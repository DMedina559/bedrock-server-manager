import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from bedrock_server_manager.web.templating import (
    configure_templates,
    get_templates,
    Jinja2Templates,
)


def test_configure_and_get_templates(mocker):
    """Test that templates are configured and retrieved correctly."""
    template_dir = Path("./test_templates")
    template_dir.mkdir(exist_ok=True)
    (template_dir / "test.html").write_text("Hello, {{ name }}!")

    mock_settings = mocker.MagicMock()
    configure_templates([template_dir], mock_settings)
    templates = get_templates()

    assert isinstance(templates, Jinja2Templates)
    template = templates.get_template("test.html")
    assert template.render({"name": "World"}) == "Hello, World!"

    # Cleanup
    (template_dir / "test.html").unlink()
    template_dir.rmdir()


def test_get_templates_not_configured():
    """Test that getting templates before configuring raises an exception."""
    # Reset the global templates object
    with patch("bedrock_server_manager.web.templating.templates", None):
        with pytest.raises(RuntimeError):
            get_templates()
