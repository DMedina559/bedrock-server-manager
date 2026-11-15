"""Independent deadlines for lifecycle preparation, including safe cancellation."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Literal

from ..error import ServerStartError
from ..events.operations import report_operation_stage
from .progress import report_stage

if TYPE_CHECKING:
    from ..config.settings import Settings


@asynccontextmanager
async def preparation_stage(
    settings: "Settings", stage: Literal["backup", "download", "install"]
) -> AsyncIterator[None]:
    phase = {
        "backup": "backing_up",
        "download": "downloading",
        "install": "installing",
    }[stage]
    report_operation_stage(phase)
    await report_stage(phase.replace("_", " ").capitalize())
    seconds = float(
        settings.get(f"lifecycle.preparation_{stage}_timeout_seconds", 600.0)
    )
    deadline = asyncio.timeout(seconds)
    try:
        async with deadline:
            yield
    except TimeoutError as error:
        if not deadline.expired():
            raise
        raise ServerStartError(
            f"Server preparation timed out during {stage} after {seconds:g} seconds. "
            "Startup was aborted; retry after checking the operation details."
        ) from error
