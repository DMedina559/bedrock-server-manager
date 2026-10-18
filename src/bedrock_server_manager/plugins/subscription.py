"""Temporary event registrations support both with and async with."""

from types import TracebackType
from typing import Callable


class EventSubscriptionScope:
    def __init__(self, register: Callable[[], str], cleanup: Callable[[str], None]):
        self._register = register
        self._cleanup = cleanup
        self._token: str | None = None
        self._entered = False

    def __enter__(self) -> str:
        if self._entered:
            raise RuntimeError("Subscription scopes cannot be entered twice")
        self._entered = True
        self._token = self._register()
        return self._token

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        token, self._token = self._token, None
        if token is not None:
            self._cleanup(token)

    async def __aenter__(self) -> str:
        return self.__enter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.__exit__(exc_type, exc, traceback)
