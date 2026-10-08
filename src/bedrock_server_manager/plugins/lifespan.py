"""Keep router resource contexts in the task that entered them."""

import asyncio
from contextlib import AsyncExitStack
from typing import Any

from fastapi import APIRouter, FastAPI


class RouterLifespan:
    def __init__(self, app: FastAPI, routers: list[APIRouter]):
        self.app = app
        self.routers = routers
        self.ready: asyncio.Future[dict[str, Any]] = (
            asyncio.get_running_loop().create_future()
        )
        self.stop = asyncio.Event()
        self.task = asyncio.create_task(self._run(), name="plugin-router-lifespan")
        self.task.add_done_callback(self._consume_error)

    @staticmethod
    def _consume_error(task: asyncio.Task[None]) -> None:
        if not task.cancelled():
            task.exception()

    async def _run(self) -> None:
        try:
            async with AsyncExitStack() as stack:
                state: dict[str, Any] = {}
                for router in self.routers:
                    value = await stack.enter_async_context(
                        router.lifespan_context(self.app)
                    )
                    state.update(value or {})
                self.ready.set_result(state)
                await self.stop.wait()
        except BaseException as error:
            if not self.ready.done():
                self.ready.set_exception(error)
            raise

    async def start(self) -> dict[str, Any]:
        try:
            return await asyncio.shield(self.ready)
        except BaseException:
            self.stop.set()
            try:
                await self.close()
            except BaseException:
                pass
            if self.ready.done() and not self.ready.cancelled():
                self.ready.exception()
            raise

    async def close(self) -> None:
        self.stop.set()
        cancelled = False
        while not self.task.done():
            try:
                await asyncio.shield(self.task)
            except asyncio.CancelledError:
                cancelled = True
            except Exception:
                break
        self.task.result()
        if cancelled:
            raise asyncio.CancelledError
