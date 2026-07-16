import pytest
from pydantic import ValidationError

from bedrock_server_manager.web.schemas.addon import AddonActionPayload
from bedrock_server_manager.web.schemas.server import AddPlayersPayload, CommandPayload
from bedrock_server_manager.web.schemas.users import (
    ChangePasswordPayload,
    ProfileUpdatePayload,
)


def test_command_payload_validation():
    """Test CommandPayload validates correctly."""
    # Valid
    payload = CommandPayload(command="stop")
    assert payload.command == "stop"

    # Invalid: empty command
    with pytest.raises(ValidationError):
        CommandPayload(command="")


def test_add_players_payload_validation():
    """Test AddPlayersPayload validates correctly."""
    # Valid
    payload = AddPlayersPayload(players=["Gamer:123"])
    assert payload.players == ["Gamer:123"]

    # Validation logic doesn't actually check the format inside the string at the pydantic level,
    # it just requires a list of strings

    # Invalid: not a list
    with pytest.raises(ValidationError):
        AddPlayersPayload(players="Gamer:123")


def test_addon_action_payload_validation():
    """Test AddonActionPayload validates correctly."""
    # Valid
    payload = AddonActionPayload(pack_uuid="123", pack_type="behavior")
    assert payload.pack_uuid == "123"

    # Invalid: missing fields
    with pytest.raises(ValidationError):
        AddonActionPayload(pack_uuid="123")


def test_profile_update_payload_validation():
    """Test ProfileUpdatePayload validates properly."""
    # Valid full update
    payload = ProfileUpdatePayload(
        email="test@test.com",
        full_name="Test User",
    )
    assert payload.full_name == "Test User"
    assert payload.email == "test@test.com"

    # Invalid partial update (both required)
    with pytest.raises(ValidationError):
        ProfileUpdatePayload(full_name="Test User")


def test_change_password_payload_validation():
    payload = ChangePasswordPayload(current_password="old", new_password="new")
    assert payload.current_password == "old"
    assert payload.new_password == "new"

    with pytest.raises(ValidationError):
        ChangePasswordPayload(current_password="old")
