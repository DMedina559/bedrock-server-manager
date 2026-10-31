# HTTP permissions and browser authentication

BSM keeps the `user`, `moderator`, and `admin` roles. HTTP routes declare
capabilities through `Security(require_permissions, scopes=[Permission.SERVERS_CONTROL])`.
Every declared capability is required. Grants come from `web/access_policy.py`;
authentication still looks up the account and its current role. These endpoint
scopes do **not** restrict an individual JWT. Selecting scopes in Swagger does
not mint a restricted token.

`GET /api/account` adds a sorted `permissions` field. The same list is available
at `GET /api/account/permissions`. User-list responses retain their existing
shape. Permissions describe static capabilities; task ownership, application-log
restrictions, local readiness checks and shutdown credentials still apply.

OpenAPI exposes the scope catalog and `x-bsm-access` version 1 on operations.
Classifications are `public`, `authenticated`, `permission`, `legacy-role`,
`custom`, and `unknown`. Metadata comes from dependencies and explicit contextual
declarations. Unknown plugin policies are never assumed public. `allowed_roles`
only describes the static policy, not a guarantee that a request succeeds.
Cookie and bearer security entries are alternatives. Cookie entries have no
OAuth scopes; both transports enforce the same application permissions.

## Credential precedence and cookies

An explicit Authorization header selects bearer authentication. Invalid,
malformed, or empty bearer credentials never fall back to a cookie account.
Without that header, the existing `access_token_cookie` JWT remains supported.
Authentication failures on protected routes return 401; insufficient permissions
return 403. Bearer permission failures include an `insufficient_scope` challenge.

Login and reauthentication retain their JSON token responses and cookie behavior:
HttpOnly, SameSite=Lax, Secure on HTTPS, trusted ingress path or `/`, and lifetime
matching the issued token. Authentication responses remain non-cacheable.
Cookies are scoped by host and path, **not TCP port**. CORS and SameSite alone
are not a complete CSRF strategy; this migration does not introduce new
cross-origin cookie workflows or change mutation CSRF enforcement.

The embedded default frontend may recover an existing cookie session via
`/api/account` and `/auth/reauth`. Saved-instance workspaces, the multi-instance
hub, standalone remote connections, and Swagger use bearer credentials without
cookies. Authentication mode participates in frontend request cancellation and
account cache identity. Older backends without access metadata remain usable;
clients label their access unknown.

## Swagger

Open `/docs` and use **Authorize** with the existing OAuth2 password endpoint.
Swagger uses a pinned Swagger UI distribution and a fetch wrapper plus request
interceptor that omit cookies for schema, login, and operation requests.
Authorization persistence is disabled. Authorizing another account therefore
does not overwrite the embedded frontend cookie. Clearing Swagger authorization
leaves protected requests unauthenticated even when a frontend cookie exists.
URLs respect the trusted ingress root path. Tokens are not copied from the SPA.

## Plugins

The legacy helpers `get_current_user`, `get_moderator_user`, and `get_admin_user`
remain available. The last two retain their actual role checks.

A plugin may register a permission during load:

```python
self.api.runtime.register_http_permission(
    "plugin:example:jobs:run", "Run example jobs", ["moderator", "admin"]
)
```

Use it in a route with `Security(require_permissions,
scopes=["plugin:example:jobs:run"])`. Names must use the plugin's own namespace.
Descriptions and explicit role grants are required; collisions and invalid names
are rejected. Registration is owned by the plugin, removed on unload or failed
load, and invalidates OpenAPI. Admin has no implicit bypass for plugin grants.
This does not change trusted in-process Python plugin access.

## Logout

Embedded logout discards its bearer token and clears the browser cookie.
Saved-instance logout discards only that instance's scoped credentials. Swagger
logout clears only Swagger authorization. The backend logout endpoint retains
its existing behavior and clears the cookie where applicable. Clearing cookies
or local credentials does not revoke JWTs retained elsewhere. Token restriction
and revocation remain separate work.
