# bedrock_server_manager/config/blocked_commands.py
"""Define a blacklist of commands that should not be sent to the Bedrock server via
certain application interfaces, typically the API or web UI.

This helps prevent accidental or malicious use of sensitive commands that could
disrupt server operation or compromise security if exposed without proper controls.
"""

API_COMMAND_BLACKLIST: list[str] = [
    "stop",  # Prevents stopping the server via general command send; use dedicated stop functions.
    "save",  # Save commands are usually managed internally or via backup systems.
    "allowlist off",  # Modifying allowlist should be through dedicated features.
]
"""
A list of command strings (or prefixes) that are blocked from being sent
through general-purpose command interfaces like the API's `send_command` endpoint.
Commands are checked case-insensitively if they start with any string in this list.
"""
