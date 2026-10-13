"""Compare bounded metadata snapshots without interpreting resets as negative activity."""

from .models import DiagnosticChange, DiagnosticComparison, DiagnosticSnapshot

_COUNTERS = {
    "attempts",
    "successes",
    "failures",
    "reload_attempts",
    "reload_successes",
    "reload_failures",
    "emitted",
    "suppressed",
    "failed_listeners",
    "successful_sends",
    "failed_sends",
    "dropped_messages",
    "send_timeouts",
    "missed_intervals",
    "load_failures",
    "drain_failures",
    "monitor_failures",
}
_SKIP = {"active", "recent", "listeners", "deliveries", "failures"}


def _values(
    snapshot: DiagnosticSnapshot,
) -> dict[tuple[str, str], float | int | bool | str | None]:
    result: dict[tuple[str, str], float | int | bool | str | None] = {}
    for section in snapshot.sections:
        result[section.name, "status"] = section.status
        result[section.name, "stale"] = section.stale
        if section.data is None:
            continue
        data = section.data.model_dump()
        for field, value in data.items():
            if field in {"kind", "plugins", "processes", "tasks", "activity"}:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                result[section.name, field] = value
            elif isinstance(value, dict):
                for key, entry in list(value.items())[:1000]:
                    if isinstance(entry, (str, int, float, bool)) or entry is None:
                        result[section.name, f"{field}.{key}"] = entry
        if "activity" in data:
            for field, value in data["activity"].items():
                if field not in _SKIP and isinstance(value, (str, int, float, bool)):
                    result[section.name, f"activity.{field}"] = value
        for plugin in data.get("plugins", [])[:100]:
            for field in (
                "status",
                "generation",
                "draining",
                "load_failures",
                "drain_failures",
            ):
                result[section.name, f"plugins.{plugin['name']}.{field}"] = plugin[
                    field
                ]
    return result


def compare_snapshots(
    before: DiagnosticSnapshot, after: DiagnosticSnapshot
) -> DiagnosticComparison:
    """Return at most 200 field changes; counter deltas require one ordered instance."""
    old, new = _values(before), _values(after)
    same = before.instance_id == after.instance_id
    ordered = after.collected_at >= before.collected_at
    changes = []
    for subsystem, field in sorted(old.keys() | new.keys()):
        previous, current = old.get((subsystem, field)), new.get((subsystem, field))
        if previous == current:
            continue
        delta = None
        counter = field.rsplit(".", 1)[-1] in _COUNTERS
        reset = counter and (not same or not ordered)
        if (
            isinstance(previous, (int, float))
            and not isinstance(previous, bool)
            and isinstance(current, (int, float))
            and not isinstance(current, bool)
        ):
            reset = reset or (counter and current < previous)
            if same and ordered and not reset:
                delta = current - previous
        changes.append(
            DiagnosticChange(
                subsystem=subsystem,
                field=field,
                before=previous,
                after=current,
                delta=delta,
                counter_reset=bool(reset),
            )
        )
        if len(changes) > 200:
            break
    return DiagnosticComparison(
        before_snapshot_id=before.snapshot_id,
        after_snapshot_id=after.snapshot_id,
        same_instance=same,
        elapsed_seconds=(
            after.collected_at - before.collected_at if same and ordered else None
        ),
        changes=changes[:200],
        truncated=len(changes) > 200,
    )
