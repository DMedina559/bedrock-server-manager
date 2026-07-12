import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.migrate import migrate


@pytest.fixture
def runner():
    return CliRunner()


def test_migrate_old_config(runner, app_context):
    """Test migrate-old-config CLI command logic executes successfully."""
    result = runner.invoke(migrate, ["old-config"], obj={"app_context": app_context})
    assert result.exit_code == 0
