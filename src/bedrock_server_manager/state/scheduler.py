"""Committed scheduler read model; all writes go through Storage transactions."""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SchedulerState:
    _records: dict[str, tuple[dict[str, Any], dict[str, Any], str | None]] = field(
        default_factory=dict, repr=False
    )

    @property
    def count(self) -> int:
        return len(self._records)

    @property
    def records(self):
        return deepcopy(self._records)

    def replace_loaded(self, rows) -> None:
        self._records = {
            name: deepcopy((configuration, state, legacy))
            for name, configuration, state, legacy in rows
        }
