import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.models import (
    DeleteServerDataRequest,
    GetBedrockProcessInfoRequest,
    GetServerRunningStatusRequest,
    InstallNewServerRequest,
    StartServerRequest,
    StopServerRequest,
    UpdateServerPlayerStatsRequest,
)


@pytest.mark.parametrize(
    "model",
    [
        DeleteServerDataRequest,
        GetBedrockProcessInfoRequest,
        GetServerRunningStatusRequest,
        InstallNewServerRequest,
        StartServerRequest,
        StopServerRequest,
    ],
    ids=lambda model: model.__name__,
)
def test_server_requests_reject_empty_name(model):
    with pytest.raises(ValidationError):
        model(server_name="")


@pytest.mark.parametrize(
    "name", ["../outside", "invalid name"], ids=["traversal", "spaces"]
)
def test_install_rejects_invalid_server_names(name):
    with pytest.raises(ValidationError):
        InstallNewServerRequest(server_name=name)


def test_player_stats_reject_mismatched_count():
    with pytest.raises(ValidationError):
        UpdateServerPlayerStatsRequest(
            server_name="test_server", player_count=2, players=[]
        )
