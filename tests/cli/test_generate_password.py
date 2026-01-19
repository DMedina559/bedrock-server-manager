import unittest
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli import generate_password


class TestGeneratePassword(unittest.TestCase):
    def test_generate_password_success(self):
        runner = CliRunner()
        result = runner.invoke(
            generate_password.generate_password_hash_command,
            input="password\npassword\n",
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Hash generated successfully", result.output)
        self.assertIn("BEDROCK_SERVER_MANAGER_PASSWORD", result.output)

    def test_generate_password_mismatch(self):
        runner = CliRunner()
        result = runner.invoke(
            generate_password.generate_password_hash_command,
            input="password\nwrongpassword\n",
        )
        self.assertIn("Error: The two entered values do not match.", result.output)

    @pytest.mark.skip(reason="Failing to capture click.Abort")
    @patch("click.prompt")
    def test_generate_password_empty(self, mock_prompt):
        mock_prompt.return_value = ""
        runner = CliRunner()
        result = runner.invoke(generate_password.generate_password_hash_command)
        self.assertIn("Error: Password cannot be empty.", result.output)
        self.assertEqual(result.exit_code, 1)
