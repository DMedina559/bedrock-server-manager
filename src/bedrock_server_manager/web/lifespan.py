"""Own application startup and shutdown for the ASGI lifespan."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..context import AppContext
from .runtime import WebRuntime


def application_lifespan(context: AppContext, runtime: WebRuntime | None):
    """Bind runtime transitions to application lifecycle completion."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await context.startup()
        try:
            if runtime is not None:
                runtime.ready()
            yield
        finally:
            try:
                await context.shutdown()
            except BaseException:
                if runtime is not None:
                    runtime.finish(failed=True)
                raise
            else:
                if runtime is not None:
                    runtime.finish()

    return lifespan
