import pytest

from bedrock_server_manager.error import (
    AppFileNotFoundError,
    BackupRestoreError,
    BlockedCommandError,
    BSMError,
    CommandNotFoundError,
    ConfigParseError,
    ConfigurationError,
    DownloadError,
    ExtractError,
    FileError,
    FileOperationError,
    InternetConnectivityError,
    InvalidServerNameError,
    MissingArgumentError,
    NetworkError,
    PermissionsError,
    SendCommandError,
    ServerError,
    ServerNotRunningError,
    ServerProcessError,
    ServerStartError,
    ServerStopError,
    SystemError,
    UserExitError,
    UserInputError,
)

# A list of all custom exception classes to be tested
exception_classes = [
    BSMError,
    FileError,
    ServerError,
    ConfigurationError,
    SystemError,
    NetworkError,
    UserInputError,
    AppFileNotFoundError,
    FileOperationError,
    DownloadError,
    ExtractError,
    BackupRestoreError,
    ServerProcessError,
    ServerStartError,
    ServerStopError,
    ServerNotRunningError,
    SendCommandError,
    ConfigParseError,
    BlockedCommandError,
    PermissionsError,
    CommandNotFoundError,
    InternetConnectivityError,
    MissingArgumentError,
    InvalidServerNameError,
]


@pytest.mark.parametrize("exc_class", exception_classes)
def test_exceptions_can_be_raised_and_caught(exc_class):
    """Tests that each custom exception can be raised and caught."""
    error_message = "This is a test error message"

    # Special case for exceptions with required arguments in __init__
    if exc_class is AppFileNotFoundError:
        with pytest.raises(exc_class) as exc_info:
            raise exc_class("/path/to/file", "Test File")
        assert str(exc_info.value) == "Test File not found at path: /path/to/file"
    elif exc_class is CommandNotFoundError:
        with pytest.raises(exc_class) as exc_info:
            raise exc_class("test_command")
        assert str(exc_info.value) == "System command not found: 'test_command'"
    else:
        with pytest.raises(exc_class) as exc_info:
            raise exc_class(error_message)
        assert str(exc_info.value) == error_message


def test_user_exit_error():
    """Tests the UserExitError specifically."""
    with pytest.raises(UserExitError):
        raise UserExitError("User exited")

    # Also test that it's a subclass of KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        raise UserExitError("User exited")


def test_exception_hierarchy():
    """Tests the inheritance hierarchy of the custom exceptions."""
    assert issubclass(FileError, BSMError)
    assert issubclass(ServerError, BSMError)
    assert issubclass(ConfigurationError, BSMError)
    assert issubclass(SystemError, BSMError)
    assert issubclass(NetworkError, BSMError)
    assert issubclass(UserInputError, (BSMError, ValueError))
    assert issubclass(UserExitError, KeyboardInterrupt)
    assert issubclass(AppFileNotFoundError, (FileError, FileNotFoundError))
    assert issubclass(FileOperationError, FileError)
    assert issubclass(DownloadError, (FileError, IOError))
    assert issubclass(ExtractError, FileError)
    assert issubclass(BackupRestoreError, FileOperationError)
    assert issubclass(ServerProcessError, ServerError)
    assert issubclass(ServerStartError, ServerProcessError)
    assert issubclass(ServerStopError, ServerProcessError)
    assert issubclass(ServerNotRunningError, ServerProcessError)
    assert issubclass(SendCommandError, ServerError)
    assert issubclass(ConfigParseError, (ConfigurationError, ValueError))
    assert issubclass(BlockedCommandError, ConfigParseError)
    assert issubclass(PermissionsError, (SystemError, PermissionError))
    assert issubclass(CommandNotFoundError, SystemError)
    assert issubclass(InternetConnectivityError, NetworkError)
    assert issubclass(MissingArgumentError, UserInputError)
    assert issubclass(InvalidServerNameError, UserInputError)
