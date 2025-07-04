# bedrock_server_manager/error.py
"""Custom exception hierarchy for the bedrock_server_manager package.

This module defines a simplified and structured set of exceptions. The design
prioritizes clarity, reduces redundancy, and integrates properly with Python's
built-in exception types.

Key Principles:
    - A single base exception, `BSMError`, for all application errors.
    - A clear hierarchy with logical categories (e.g., FileError, ServerError).
    - Inheritance from standard Python exceptions (e.g., ValueError, FileNotFoundError)
      to allow for flexible and standard exception handling.
"""

# --- Base Exception ---


class BSMError(Exception):
    """Base class for all custom exceptions in this project."""

    pass


# --- Primary Exception Categories ---


class FileError(BSMError):
    """Base for errors related to file or directory operations."""

    pass


class ServerError(BSMError):
    """Base for errors related to managing the Bedrock server process."""

    pass


class ConfigurationError(BSMError):
    """Base for errors related to configuration files or values."""

    pass


class SystemError(BSMError):
    """Base for errors related to interactions with the host operating system."""

    pass


class NetworkError(BSMError):
    """Base for errors related to network connectivity."""

    pass


class UserInputError(BSMError, ValueError):
    """
    Base for errors caused by invalid user input.
    Inherits from `ValueError` for broader compatibility.
    """

    pass


class UserExitError(KeyboardInterrupt):
    """
    Raised for graceful exits initiated by the user (e.g., answering 'no' to a prompt).
    Inherits from `KeyboardInterrupt` so it's not caught by a broad `except Exception`.
    """

    pass


# --- Specific Exceptions by Category ---


# File and Directory Errors
class AppFileNotFoundError(FileError, FileNotFoundError):
    """
    Raised when an essential application file or directory is not found.
    Inherits from `FileNotFoundError` for standard exception handling.
    """

    def __init__(self, path: str, description: str = "Required file or directory"):
        self.path = path
        self.description = description
        super().__init__(f"{self.description} not found at path: {self.path}")


class FileOperationError(FileError):
    """Raised for general failures during file operations like copy, move, or delete."""

    pass


class DownloadError(FileError, IOError):
    """Raised when downloading a file fails. Inherits from IOError."""

    pass


class ExtractError(FileError):
    """Raised when extracting an archive (zip, etc.) fails."""

    pass


class BackupRestoreError(FileOperationError):
    """Raised when a backup or restore operation fails."""

    pass


# Server Process and Communication Errors
class ServerProcessError(ServerError):
    """Base for errors in starting, stopping, or checking the server process."""

    pass


class ServerStartError(ServerProcessError):
    """Raised when the server process fails to start."""

    pass


class ServerStopError(ServerProcessError):
    """Raised when the server process fails to stop."""

    pass


class ServerNotRunningError(ServerProcessError):
    """Raised when an operation requires the server to be running, but it's not."""

    pass


class SendCommandError(ServerError):
    """Raised when sending a command to the server console fails."""

    pass


# Configuration Errors
class ConfigParseError(ConfigurationError, ValueError):
    """
    Raised when a configuration file is malformed or contains invalid values.
    Inherits from `ValueError` for standard exception handling.
    """

    pass


class BlockedCommandError(ConfigParseError):
    """Raised when an attempt is made to send a command blocked by configuration."""

    pass


# System and Environment Errors
class PermissionsError(SystemError, PermissionError):
    """
    Raised for OS-level file or directory permission errors.
    Inherits from `PermissionError` for standard exception handling.
    """

    pass


class CommandNotFoundError(SystemError):
    """Raised when a required system command (e.g., 'systemctl', 'unzip') is not found."""

    def __init__(self, command_name: str, message="System command not found"):
        self.command_name = command_name
        self.message = message
        super().__init__(f"{self.message}: '{self.command_name}'")


# Network Errors
class InternetConnectivityError(NetworkError):
    """Raised when an operation requires internet access, but it's unavailable."""

    pass


# User Input Errors
class MissingArgumentError(UserInputError):
    """Raised when a required function or command-line argument is missing."""

    pass


class InvalidServerNameError(UserInputError):
    """Raised when a provided server name is invalid or contains illegal characters."""

    pass
