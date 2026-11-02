# HTTP API and clients

BSM exposes a typed HTTP API for integrations and the frontend. While the host is running, `/docs` provides interactive documentation and `/api/openapi.json` provides FastAPI's schema. Inspect the running installation's schema before constructing requests; model fields and routes can change between releases.

## Authenticate

- **Named integration tokens (recommended for scripts and automation):** Create a scoped integration token (`bsm_it_...`) under **Account → Integrations** (`POST /api/account/tokens`) with only the permissions and servers the integration requires, and pass `Authorization: Bearer bsm_it_...`. Integration tokens survive interactive session logouts and can be rotated or revoked independently.
- **Interactive login sessions:** Submit form-encoded `username` and `password` (plus `otp` when MFA is enabled, or complete WebAuthn passkey authentication via `/auth/passkey/options` and `/auth/passkey/verify`) to `POST /auth/token`. By default, `POST /auth/token` returns a bearer JWT (`Authorization: Bearer TOKEN`). Browser sessions send `X-BSM-Auth-Mode: cookie` to use an `HttpOnly` session cookie and supply `X-CSRF-Token` (from `X-BSM-CSRF-Token`) on state-changing requests.

Do not put tokens in URLs or commit them to scripts. Permissions are enforced by route dependencies (`x-bsm-access` in OpenAPI); see [HTTP permissions and browser authentication](../developer/http_access.md) and the [shutdown guide](web_runtime.md).

## Handle responses

Validate successful response bodies against the endpoint's schema. For asynchronous operations, follow the returned task information through completion instead of treating acceptance as success. Distinguish validation errors, authentication/authorization failures, unavailable runtime state and domain-operation failures.

During shutdown, new mutations receive HTTP 503. A shutdown response with HTTP 202 confirms acceptance, not completed cleanup. Avoid blindly retrying destructive operations after a lost connection; inspect current server/task state first.

## Upgrade integrations

Regenerate generated clients from the backend schema after contract changes. Verify request names, nullable fields, response models and error handling against the installed backend. Plugin-defined routes have their own contracts and authentication requirements.

Use [WebSockets](websockets.md) for live notifications; use HTTP state reads to reconcile after reconnecting.
