from click.testing import CliRunner

from bedrock_server_manager.cli.migrate import migrate_old_config
from bedrock_server_manager.db.models import Setting


def test_migrate_old_config_json_structure(app_context):
    """
    Test that migrate_old_config modifies the JSON content of 'web' and 'logging' settings.
    """
    # 1. Setup Data with "web" and "logging" rows containing the deprecated keys
    with app_context.db.session_manager() as db:
        # Add 'web' setting (JSON object)
        db.add(Setting(key="web", value={"host": "0.0.0.0", "threads": 4}))

        # Add 'logging' setting (JSON object)
        db.add(Setting(key="logging", value={"cli_level": 20, "file_level": 10}))

        db.commit()

        # Verify insertion
        web_setting = db.query(Setting).filter_by(key="web").first()
        logging_setting = db.query(Setting).filter_by(key="logging").first()
        assert "threads" in web_setting.value
        assert "cli_level" in logging_setting.value
        assert "file_level" in logging_setting.value

    # 2. Run migration
    runner = CliRunner()
    result = runner.invoke(migrate_old_config, obj={"app_context": app_context})

    # Assert successful execution
    assert result.exit_code == 0

    # 3. Verify JSON modification
    # We must start a NEW transaction/session to see changes committed by the CLI command
    with app_context.db.session_manager() as db:
        web_setting = db.query(Setting).filter_by(key="web").first()
        logging_setting = db.query(Setting).filter_by(key="logging").first()

        print(f"DEBUG TEST: Web Value: {web_setting.value}")
        print(f"DEBUG TEST: Logging Value: {logging_setting.value}")

        # Expectation: "threads" should be gone from "web"
        assert (
            "threads" not in web_setting.value
        ), f"web.threads still exists: {web_setting.value}"

        # Expectation: "cli_level" and "file_level" gone from "logging", "level" added
        assert (
            "cli_level" not in logging_setting.value
        ), f"logging.cli_level still exists: {logging_setting.value}"
        assert (
            "file_level" not in logging_setting.value
        ), f"logging.file_level still exists: {logging_setting.value}"
        assert (
            "level" in logging_setting.value
        ), f"logging.level missing: {logging_setting.value}"
        assert logging_setting.value["level"] == 10  # value migrated from file_level
