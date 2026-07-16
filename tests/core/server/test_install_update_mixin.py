import os
from unittest.mock import patch


def test_is_update_needed_no_exe(real_bedrock_server):
    """Test update needed if executable doesn't exist."""
    server = real_bedrock_server
    os.remove(server.bedrock_executable_path)
    assert server.is_update_needed("1.20.0") is True


def test_is_update_needed_specific_version(real_bedrock_server):
    """Test update needed against specific version."""
    server = real_bedrock_server
    with patch.object(server, "get_version", return_value="1.19.0"):
        assert server.is_update_needed("1.20.0") is True
        assert server.is_update_needed("1.19.0") is False
