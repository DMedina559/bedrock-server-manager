# HTTP API and clients

BSM exposes a typed HTTP API for integrations and the frontend. While the host is running, `/docs` provides interactive documentation and `/api/openapi.json` provides FastAPI's schema. Inspect the running installation's schema before constructing requests; model fields and routes can change between releases.

## Authenticate

Submit form-encoded `username` and `password` to `POST /auth/token`. The response contains an access token. Clients authenticate protected calls with `Authorization: Bearer TOKEN`; browser sessions also use BSM's cookie authentication.

Do not put tokens in URLs or commit them to scripts. Permissions are enforced by route dependencies; administrator-only runtime control is described in the [shutdown guide](web_runtime.md).

## Handle responses

Validate successful response bodies against the endpoint's schema. For asynchronous operations, follow the returned task information through completion instead of treating acceptance as success. Distinguish validation errors, authentication/authorization failures, unavailable runtime state and domain-operation failures.

During shutdown, new mutations receive HTTP 503. A shutdown response with HTTP 202 confirms acceptance, not completed cleanup. Avoid blindly retrying destructive operations after a lost connection; inspect current server/task state first.

## Upgrade integrations

Regenerate generated clients from the backend schema after contract changes. Verify request names, nullable fields, response models and error handling against the installed backend. Plugin-defined routes have their own contracts and authentication requirements.

Use [WebSockets](websockets.md) for live notifications; use HTTP state reads to reconcile after reconnecting.
