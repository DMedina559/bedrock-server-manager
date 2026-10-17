"""Read-only observations exposed to a local process supervisor."""

from pydantic import BaseModel, ConfigDict

from ...api.models.health import GetApplicationHealthResponse
from ..runtime import RuntimeStatus


class RuntimeReadinessResponse(BaseModel):
    """Bind application health and installed version to one runtime instance."""

    model_config = ConfigDict(extra="forbid")
    runtime: RuntimeStatus
    version: str
    health: GetApplicationHealthResponse
