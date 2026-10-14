# State, storage and service mutations

`AppState` holds validated persistent records and separate runtime observations. `ChangeSet` tracks pending state persistence. `Storage` coordinates loads, flushes and database transactions; repositories encapsulate row access. Application services own domain mutations.

## Mutation boundaries

Validate the candidate before writing. Service mutations acquire the relevant locks, commit database changes, then publish the new in-memory record. A failed commit must not appear as a successful state update. Revisions order observations; they do not prove an atomic fleet-wide snapshot.

Use supported service/storage methods instead of writing a database row and separately editing state. Preserve the established lock order when combining record locks and storage writes. Configuration-file operations have their own locks and are not part of an atomic database/filesystem transaction.

Runtime process handles and live metrics are not persistent configuration. Avoid mutating returned data to save changes: submit a validated update through its owner. Typed update models distinguish omitted fields from explicitly supplied values.

## Database evolution

Add schema changes under `db/migrations/versions`; preserve an upgrade path for existing installations. Test migration from the preceding schema, reopening the database and retained data. Package migration resources with the application. Database rollback requires a compatible backup, not merely an older Python package.

The tests use isolated file-backed databases and a migrated template for ordinary cases. Migration tests create their own starting schema. Never share sessions, mutable application state or event-loop resources between tests.

See [state](reference/state/index.rst), [storage](reference/storage/index.rst) and [service references](reference/services/index.rst). Diagnostic history uses independent transactions and must never alter the outcome of an observed domain transaction.
