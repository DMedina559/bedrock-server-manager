# State, storage, and application typing audit

Reviewed the Pydantic branch after commit
`29e830f4a282bc12660241b60ea4b513442316b4` (same application tree as local
`bda4456`). Findings below describe that baseline. The implementation follow-up
addresses them on the Pydantic branch.

## Implementation follow-up

- Strict, finite, default-validated persistent/settings/statistics records;
  constrained ports, retry/retention counts, intervals and runtime statistics.
- Frozen settings sections and snapshot container/entity-map reads. Use
  SettingsState.set or services to persist updates; modifying a returned mapping
  does not modify live state. Assignment of a complete settings root is validated
  and marks that root dirty.
- One settings lock and one live state source, with the old `_settings` accessor
  retained as a derived snapshot. Settings defaults come from the state schema.
- Consistent plugin shorthand routing, explicit null writes, and preservation of
  legacy extension roots under custom. Known legacy numeric strings and the
  `max_retiries` spelling are normalized only during DB loading.
- Validated task records with atomic transitions and JSON-safe stored results.
- State-aware server deletion serialized with flush/reload, with dirty flags
  acknowledged after commit and preserved on failure.
- Typed partial service update records. Omitted nullable fields retain their
  value; explicitly supplied null clears user/plugin optional fields.
- SQLAlchemy DeclarativeBase/Mapped models and typed repository sessions, plus
  generic storage snapshot helpers. All eight table definitions compile to the
  same SQL as before for SQLite, PostgreSQL and MySQL.
- Type-aware JSON equality in no-op detection and post-commit acknowledgement.
  JSON updates are explicitly flagged so SQLAlchemy does not suppress a `1` to
  `true` change through Python equality.
- Resolved bootstrap configuration validation preserving CLI/environment/file
  precedence and JSON extensions. Core process, summary, allowlist, permission
  and addon-manifest boundaries validate known data and preserve supported
  external JSON extensions.
- The plugin API generator now emits `Mapping[str, object]` so `--check` agrees
  with the generated protocol file. Generated artifacts must be changed through
  their generator.

Focused regressions exercise invalid settings without partial mutation, legacy
loading, explicit null updates, type changes during commits, failed/concurrent
deletion, invalid task results, snapshot isolation, and external format extensions.

Implementation validation: all pre-commit hooks pass (including Black, isort,
flake8 and mypy); generated API types and 113 deferred/direct caller signatures
pass their checks. The local full-suite run reports 1001 passed, 2 skipped and
4 capability exclusions for the previously reproduced DNS/procfs-dependent
tests. The focused minimum-Pydantic-2.9.2 suite reports 144 passed. GitHub's
Python 3.11/3.14 workflow runs the unfiltered suite.

## Existing architecture

Pydantic is already used for persistent server/plugin/user records, settings
sections, bans, and server runtime statistics. Storage connects those records to
SQLAlchemy repositories. AppState, entity collections, ChangeSet and PluginRuntime
remain dataclasses. This separation is useful: validation belongs on data records
and external boundaries, while locks, sessions and task execution belong in
runtime managers.

Keep SQLAlchemy as the persistence mechanism. Improve ORM annotations with
`DeclarativeBase`, `Mapped[T]`, `mapped_column` and typed `AsyncSession` repository
parameters. Preserve explicit existing nullability/defaults during that migration:
SQLAlchemy can infer schema properties from annotations, so this must include a
schema comparison. Pydantic can validate loaded ORM attributes or explicit record
mappings; it does not replace transactions, relationships or database migrations.

## Reproduced findings

| Priority | Finding and evidence | Recommended correction |
| --- | --- | --- |
| High | Settings accept `web.port=999999`, `retention.backups=-5`, and `monitoring.process_interval_sec=-1`. The failure is deferred to consumers. | Bound ports to 1–65535, retention/retries to nonnegative integers, and monitoring intervals/token duration to positive values. Preserve valid zero-retention/retry behavior. |
| High | After `PluginService.set_setting`, the live state has the new plugin settings but `get_all_global_settings` returns the older `Settings._settings` cache. | Read bulk settings from the current state snapshot; remove or derive the duplicate cache. |
| High | A background task with no notification username accepts `{'value': NaN}` and records `status='completed'`; retrieving its TaskSnapshot raises ValidationError. | Validate/normalize a candidate task record before changing live state. Configure its JSON adapter for strict, finite data and store its validated result. |
| Medium | Persistent/settings models still coerce values: `'8080'` becomes an integer and server `autostart='true'` becomes True. API base strictness does not reach these separate bases. | Establish strict domain-record/settings bases with validated defaults, finite JSON values and instance revalidation. Handle old DB formats in an explicit migration/normalization step. |
| Medium | `SettingsState.get('example.enabled')` reads `plugin_settings['example']`, but `set('example.enabled', True)` writes `custom['example']`, shadowing the plugin namespace while leaving the canonical value unchanged. | Define one lookup/write resolution policy; prefer canonical `plugin_settings.example.enabled` and an explicit compatibility adapter if shorthand is supported. |
| Medium | `SettingsService.update_setting('missing', None)` makes no change and no persistence call because absent keys and explicit null compare equal. | Use a missing sentinel and distinguish existence from value before deciding a write is a no-op. |
| Medium | `SettingsState.from_dict({'legacy_extension': {'value': 1}})` silently omits that root from loaded state even though the model advertises forbidden extras. | Validate the complete normalized mapping; migrate known legacy extensions into custom/plugin namespaces and diagnose other unknown keys. Do not silently discard them. |
| Medium | Direct `settings.web.port=9000` changes live state without marking it dirty. Mutating `settings.custom` in place can insert a non-JSON object without validation. | Encapsulate live mutable containers and use validated copy-and-set operations through services. Assignment validation alone does not validate dictionary mutations or implement dirty tracking. |
| Medium | `RuntimeState.set_server_runtime` accepts a constructed record with `running='invalid'` and `players_online=-3`; copying preserves invalid fields. | Give runtime statistics appropriate strict constraints and revalidate snapshots on ingress, then copy them. |
| Medium | Deleting an already dirty server through the repository/live-map pattern used by InstallationMixin leaves its name dirty forever: a subsequent Storage.flush skips the missing record and never acknowledges it. Reproduced with a real SQLite database. | Add a state-aware deletion operation with transactional deletion, dirty-key cleanup and a clear concurrency policy. Test deletion concurrent with flush/reload; Pydantic alone cannot solve it. |

Relevant implementation files:

- `state/settings.py`: settings bases, constraints, get/set resolution and loading.
- `state/models.py`: persistent records and runtime snapshot ingress.
- `services/settings_service.py`: missing/null no-op detection and cached settings.
- `services/plugin_service.py` and `api/settings.py`: stale bulk-settings path.
- `web/tasks.py`: task-result validation and mutable task dictionaries.
- `db/storage.py` and `core/server/installation_mixin.py`: deletion/dirty tracking.

The mutation and constructed-runtime examples demonstrate validation/design gaps;
they do not establish that ordinary application callers currently use every unsafe
path. The stale bulk-settings and missing/null examples exercise actual service
and API entry points. Unknown settings remain in the DB; the demonstrated problem
is omission from the loaded state, not proven deletion of the DB row.

## Additional Pydantic opportunities

1. **TaskRecord**: a dedicated internal record for task status/message/result/error/
   owner, with futures kept separately. TaskSnapshot is already a typed public
   contract; internal task dictionaries should have an equally reliable shape.
2. **Bootstrap configuration**: validate resolved CLI/environment/file settings
   for data directory, DB URL, log level and web options. Preserve existing
   precedence. A resolved Pydantic model may suffice; adopting pydantic-settings
   is optional and should not accidentally change precedence.
3. **Core data boundaries**: typed process statistics, server summaries,
   allowlist/permission entries, addon manifests and pack activation records.
   Validate once when reading external data and keep typed data through core/API
   layers. Minecraft/plugin extension formats may need preserved extra fields;
   blanket `extra='forbid'` is inappropriate for every external format.
4. **Service update records**: replace dictionary assembly and selected Any
   annotations with explicit update models or typed signatures. Updates that must
   clear optional fields need to distinguish omitted fields from explicit null.
5. **One settings schema/default source**: derive Settings.default_config from the
   state models instead of maintaining parallel defaults.

Keep AppState, Storage, DB sessions, locks and running task handles as ordinary
runtime objects. ChangeSet's internal set-of-keys representation is also reasonable;
convert it to a transport model only when an external boundary requires that.

## Validation and implementation sequence

Existing state/storage/repository/service/settings/task tests: **55 passed**.
Separate direct reproductions confirmed the table's cases, including real SQLite
deletion. The passing suite currently does not cover these cases.

Recommended order:

1. Fix stale settings reads, missing/null writes, task-result admission and
   state-aware deletion; add focused regressions.
2. Add settings bounds and strict record bases with tests for existing legacy
   settings, including `monitoring.max_retiries` migration and flattened DB keys.
3. Improve repository/ORM typing and remove Any from storage snapshots using
   concrete helpers or generic protocols without mismatching domain/save types.
4. Extend typed core data and bootstrap configuration incrementally.

References:

- https://docs.pydantic.dev/latest/concepts/models/
- https://docs.pydantic.dev/latest/api/config/
- https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html
