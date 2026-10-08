# Pydantic transition audit

Audited branch: `refactor!/move-api-to-pydantic`, commit
`833eb28fde7b5a43140933405aa5fb0f4700eddd`.

## Findings and changes

The migration already provides operation-specific request/response models,
strict validation, forbidden extra fields, instance revalidation, and separate
input/output error handling. Cancellation and response validation occur before
after-events publish results. These foundations should remain.

| Finding | Change |
| --- | --- |
| `JsonValue` accepted NaN/infinity, which can serialize as null and lose information. | Both API base models now reject non-finite floats, including nested JSON values. |
| Defaults bypassed the strict validation applied to caller-supplied values. | Both API bases now validate defaults. |
| Mypy did not enable Pydantic's plugin. | Enabled the plugin and added stricter annotation/container checks specifically for API model modules. The plugin respects strict constructors and frozen fields. |
| Bridge mapping inputs used `Any`, despite representing unvalidated data. | Data API protocols now accept `Mapping[str, object]`; runtime callbacks keep their dynamic signatures. |
| Some known response fields were assembled as dictionaries, bypassing constructor type checks. | Five settings write/reload response builders now use typed constructors. Runtime settings reads still validate mappings. |
| Contract documentation reported outdated operation counts. | Updated totals to 80 data operations, 61 registered APIs, and 57 plugin-visible APIs. |

Added regression coverage for scalar and nested non-finite numbers, invalid
defaults on both API bases, and JSON round trips preserving scalar types.
Also completed the contract binder's return annotation and schema callback's
generic model annotation.

## Practical follow-ups

- Continue replacing `model_validate({...})` with constructors when all response
  fields are known. Retain mapping validation for database/core/transport data;
  avoid casts that merely disguise unvalidated values.
- Keep `JsonValue` for extensible settings and event payloads. Give stable domain
  records concrete models rather than imposing one schema on arbitrary plugin
  data.
- Frozen models are shallow: nested lists/dictionaries remain mutable. Boundary
  revalidation and event deep copies already address the relevant validation
  paths. A switch to tuples would change callers and warrants separate work.
- The separately released `bsm-cli` and third-party plugins need the new request
  signatures and exception contracts before adopting this branch. They are not
  included in this repository audit.
- Expand strict static checks by module as runtime code gains annotations. A
  global strict switch would introduce unrelated work across CLI, process, and
  transport modules.

## Validation

- Full suite: 966 passed, 2 skipped, 4 environment failures reproduced on the
  untouched branch.
- Focused API, plugin-contract, plugin-caller and HTTP-schema suite: 289 passed.
- Settings/server/caller checks after constructor cleanup: 29 passed.
- Contract suites with minimum supported Pydantic 2.9.2: 109 passed.
- Mypy: all 192 source files pass; repository-wide check covers 327 Python files.
- API signature checker: 113 calls checked, including deferred task targets.
- Formatting, import ordering, targeted lint and whitespace checks pass.

The four connectivity/process failures in the full test run also fail
on the untouched branch: DNS access to `clients3.google.com` is unavailable and
the runtime has no `/proc` filesystem for psutil/process discovery. An existing
server test also emits an unawaited `AsyncMock` warning for a synchronous lock
release.
