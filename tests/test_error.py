"""
Tests for the error.py module.
"""

from bedrock_server_manager.error import (
    AppFileNotFoundError,
    BSMError,
    CommandNotFoundError,
    MissingArgumentError,
    UserInputError,
)


def test_bsm_error_base():
    """Test that base error initializes correctly."""
    err = BSMError("test error")
    assert str(err) == "test error"


def test_app_file_not_found_error():
    """Test AppFileNotFoundError properly formats its message."""
    err = AppFileNotFoundError("/some/path", "My config")
    assert err.path == "/some/path"
    assert err.description == "My config"
    assert str(err) == "My config not found at path: /some/path"
    assert isinstance(err, FileNotFoundError)


def test_command_not_found_error():
    """Test CommandNotFoundError properly formats its message."""
    err = CommandNotFoundError("unzip", "Cannot find command")
    assert err.command_name == "unzip"
    assert err.message == "Cannot find command"
    assert str(err) == "Cannot find command: 'unzip'"


def test_user_input_error_inherits_value_error():
    """Test UserInputError correctly inherits from ValueError."""
    err = UserInputError("Bad input")
    assert isinstance(err, ValueError)


def test_missing_argument_error():
    """Test MissingArgumentError inherits from UserInputError."""
    err = MissingArgumentError("Missing arg")
    assert isinstance(err, UserInputError)
