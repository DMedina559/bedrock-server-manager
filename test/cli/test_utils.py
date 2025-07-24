import unittest
from unittest.mock import MagicMock, patch

import click
import pytest

from bedrock_server_manager.cli import utils


class TestUtils(unittest.TestCase):
    def test_handle_api_response_success(self):
        response = {
            "status": "success",
            "message": "Test success",
            "data": {"key": "value"},
        }
        result = utils.handle_api_response(response, "Default success")
        self.assertEqual(result, {"key": "value"})

    def test_handle_api_response_error(self):
        response = {"status": "error", "message": "Test error"}
        with self.assertRaises(click.Abort):
            utils.handle_api_response(response, "Default success")
