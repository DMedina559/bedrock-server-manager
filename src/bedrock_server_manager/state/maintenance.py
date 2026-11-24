"""Reject independent mutations during a server's coordinated maintenance."""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator
from uuid import uuid4

from ..error import OperationConflictError

_tokens: ContextVar[dict[int, str]] = ContextVar("server_maintenance", default={})


class MaintenanceGuard:
    """Permit nested lifecycle/recovery work while rejecting unrelated writers."""

    def __init__(self) -> None:
        self.active: str | None = None

    def check(self) -> None:
        if self.active is not None and _tokens.get().get(id(self)) != self.active:
            raise OperationConflictError(
                "Server settings are locked by restore maintenance."
            )

    @contextmanager
    def hold(self) -> Iterator[None]:
        self.check()
        if self.active is not None:
            yield
            return
        identifier = uuid4().hex
        self.active = identifier
        token = _tokens.set({**_tokens.get(), id(self): identifier})
        try:
            yield
        finally:
            self.active = None
            _tokens.reset(token)
