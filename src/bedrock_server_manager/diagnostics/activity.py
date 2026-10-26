"""Bound event detail projections and aggregate recent outcomes in fixed buckets."""

import time
from collections import Counter, deque
from collections.abc import Callable

from ..events.models import EventDiagnostics, EventSubscriptions
from ..operations import OperationActivity
from .models import RecentDiagnosticCounts, RecentDiagnosticWindow


def bound_event_activity(
    activity: EventDiagnostics, *, records: int, details: int
) -> tuple[EventDiagnostics, bool]:
    """Copy and limit nested records without mutating the event bus observation."""
    result = activity.model_copy(deep=True)
    result.active_truncated = result.active_truncated or len(result.active) > records
    result.recent_truncated = result.recent_truncated or len(result.recent) > records
    truncated = result.active_truncated or result.recent_truncated
    result.active = result.active[:records]
    result.recent = result.recent[:records]
    for record in result.active + result.recent:
        record.cancellation_reason = None
        for field in ("listeners", "failures", "deliveries"):
            values = getattr(record, field)
            truncated = truncated or len(values) > details
            setattr(record, field, values[:details])
    return result, truncated


def bound_operations(activity: OperationActivity, *, records: int) -> OperationActivity:
    """Bound operation detail even when a provider returns an oversized view."""
    result = activity.model_copy(deep=True)
    result.active_truncated = result.active_truncated or len(result.active) > records
    result.recent_truncated = result.recent_truncated or len(result.recent) > records
    result.active = result.active[:records]
    result.recent = result.recent[:records]
    return result


def bound_subscriptions(
    snapshot: EventSubscriptions, *, records: int, details: int
) -> EventSubscriptions:
    """Bound both listener count and ordering-reference detail in support reports."""
    result = snapshot.model_copy(deep=True)
    result.truncated = result.truncated or len(result.items) > records
    result.items = result.items[:records]
    for item in result.items:
        for field in ("before", "after", "unresolved_before", "unresolved_after"):
            values = getattr(item, field)
            result.truncated = result.truncated or len(values) > details
            setattr(item, field, values[:details])
    return result


class RecentOutcomes:
    """Keep 31 ten-second buckets, independent of journal write availability."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.started = clock()
        self.buckets: deque[tuple[int, Counter[tuple[str, str]]]] = deque(maxlen=31)

    def record(self, subsystem: str, outcome: str, code: str) -> None:
        stamp = int(self.clock() // 10)
        if not self.buckets or self.buckets[-1][0] != stamp:
            self.buckets.append((stamp, Counter()))
        if outcome in {"failed", "cancelled"}:
            self.buckets[-1][1][subsystem, outcome] += 1
        if "timeout" in code:
            self.buckets[-1][1][subsystem, "timeouts"] += 1

    def snapshot(self) -> RecentDiagnosticWindow:
        now = self.clock()
        cutoff = int(now // 10) - 29
        totals: Counter[tuple[str, str]] = Counter()
        for stamp, counts in self.buckets:
            if stamp >= cutoff:
                totals.update(counts)
        by_subsystem = {}
        for subsystem, _ in totals:
            by_subsystem[subsystem] = RecentDiagnosticCounts(
                failed=totals[subsystem, "failed"],
                cancelled=totals[subsystem, "cancelled"],
                timeouts=totals[subsystem, "timeouts"],
            )
        return RecentDiagnosticWindow(
            observed_since=time.time() - min(300, max(0, now - self.started)),
            failures=sum(item.failed for item in by_subsystem.values()),
            cancelled=sum(item.cancelled for item in by_subsystem.values()),
            timeouts=sum(item.timeouts for item in by_subsystem.values()),
            by_subsystem=by_subsystem,
        )
