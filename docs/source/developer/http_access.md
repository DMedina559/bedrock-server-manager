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

Login, setup, and reauthentication default to bearer mode: JSON contains the
JWT and no authentication cookie is set. The embedded frontend explicitly sends
`X-BSM-Auth-Mode: cookie`: the JSON access token is empty and the JWT stays in an
HttpOnly, SameSite=Lax cookie (Secure on HTTPS). The SPA never copies it into
JavaScript storage. Saved instances, remote connections, SDKs, and Swagger use
bearer mode. Authentication responses are non-cacheable.

Cookie mutations require `X-CSRF-Token`, obtained from the response header
`X-BSM-CSRF-Token`, and reject a mismatching Origin. Cookie WebSockets require
a same-origin Origin. Explicit bearer requests are exempt from CSRF checks.
Only trusted ingress peers can supply the forwarded public host. Cookies are
scoped by host and path, not TCP port. Authentication mode participates in request
cancellation and account cache identity.

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

`POST /auth/logout` revokes the current login session and closes its live
connections. Cookie mode also clears its cookie. The deprecated GET shim remains
hidden from OpenAPI. Refreshing a JWT retains its session ID and original
absolute deadline. Swagger's local authorization clear only forgets its bearer.
Account security settings can revoke individual logins, other logins, or every
login. Integration credentials are managed separately and survive session logout.
A client receiving `X-BSM-Session-Invalid: 1` must request an explicit sign-in;
the SDK does not silently authenticate again with a saved password.

## Account security

The Account page provides Sessions, Integrations, My access, Activity, and
Password & MFA tabs. Session labels, user agents, and IPs are informational hints,
not proof of device identity. Last activity includes authenticated background
polling. Administrators can inspect and revoke another account's sessions and
reset its MFA. Password resets revoke existing logins; changing your own password
keeps the verified current session. Integration credentials remain independent.

`security.session_idle_hours` defaults to 24 (range 1–672), and
`security.session_max_days` defaults to 28 (range 1–90). Non-remembered logins
last at most 24 hours. Remembered logins are capped by the configured maximum.
Sensitive account and administrator changes require password verification within
five minutes, plus a factor when MFA is enabled. Refresh does not renew this proof.
Authentication attempts are limited per peer and account in five-minute windows;
a successful login resets its account failure budget.

Authenticator enrollment expires after ten minutes. TOTP codes cannot be replayed.
Ten one-use recovery codes are displayed once; save them securely. Replacing them
invalidates the old set. Enabling or disabling MFA revokes other login sessions.
Back up the database together with `config/security/mfa.key` (relative to the
installation configuration directory). The key encrypts authenticator secrets;
losing it requires recovery codes or an administrator MFA reset. Recovery codes
are stored as hashes. Security activity is retained for 90 days with opportunistic
cleanup; it excludes passwords, bearer credentials, and authenticator secrets.

Upgrading requires one new sign-in: older JWTs without a tracked session are
rejected. Database migration creates the session and MFA records automatically.

## Named integration credentials

`POST /api/account/tokens` issues a named bearer credential, returned once as
`token`. Supply `name`, explicit `permissions`, optional immutable `server_ids`,
and `expires_in_days` (1–365, default 30). `GET /api/account/tokens` returns only
metadata; `DELETE /api/account/tokens/{token_id}` revokes it. Admins can list or
revoke another account's credentials through `/api/access/users/{user_id}/tokens`.
There are at most 100 live credentials per account. Only a SHA-256 digest is
stored; the random secret is never stored, logged, or placed in task records.
Last-use timestamps are updated at most once per minute.

An integration credential always intersects its explicit capabilities with the
owner's **current** role and server assignments. Revocation, expiry, disabling or
deleting the owner, and role reductions take effect on subsequent requests and
socket deliveries. Integration credentials cannot manage accounts, permissions,
or credentials, and cannot exchange themselves for an unrestricted JWT.
They must be supplied as bearer headers or the WebSocket authentication frame,
never cookies or URL parameters. Swagger's IntegrationToken bearer scheme accepts
a pasted named credential. Logging out of a client discards its local copy;
revocation is an explicit, separate operation.

## Assigned servers

Existing accounts keep access to all servers allowed by their role. Admins can
use `PUT /api/access/users/{user_id}/servers` to replace an account's assignments
with `{ "mode": "assigned", "grants": [{ "server_id": "...", "permissions":
["servers:read"] }] }`. `mode: all` restores the role's ordinary server access.
`GET` reads assignments. `GET /api/access/servers` lists visible immutable IDs
and effective capabilities; `GET /api/access/policy` supplies the catalog and
role ceilings. Every server grant must include `servers:read`.

Assignments narrow access; they never elevate a role. Use moderator or user
accounts for scoped operators. Admin accounts and an administrator's own access
cannot be restricted through this endpoint. A token can further restrict any
owner's resources. Server-restricted principals lose host-wide capabilities
such as application settings, global backup keys, and application metrics.
Public appearance settings and icon assets remain public; these assignments
are operational authorization, not a redesign of public presentation data.

Users and servers have immutable identities. Deleting and recreating a name
cannot transfer grants or integration credentials. Newly issued JWTs also carry
the account identity and a tracked session; older JWTs require a new sign-in. Ordinary server backups do not export
account grants or credentials; those reside in the application database.

## Changes, tasks, and sockets

`GET /api/account` includes `policy_revision`, `server_access`, effective
`server_permissions` keyed by immutable ID, and the current `credential_id` when
applicable. Responses expose `X-BSM-Policy-Revision` through CORS. Policy revision
changes invalidate frontend account caches and reload the live API explorer.
Socket control messages `access_changed`, `policy_changed`, and
`credentials_changed` contain no secrets. Notifications are advisory; request
and delivery checks read committed access state. Creating a credential does not
reset the session or erase its one-time secret display.

Task records capture the initiating account identity, credential ID, resource,
and required capabilities. Restricted principals can only read authorized task
results; different integration credentials cannot read each other's tasks.
Socket subscriptions and each delivery enforce the current resource and
capability restrictions. Unknown plugin/global topics are unavailable to
restricted principals. Legacy plugin routes without explicit permission
policies remain available to ordinary unrestricted sessions, but fail closed for
integration credentials and assigned-server sessions. Plugins should declare
permissions and explicitly authorize each resource in collection endpoints.


Integration credentials can be rotated with
`POST /api/account/tokens/{token_id}/rotate`. Rotation atomically revokes the old
secret and returns its replacement once, preserving the original absolute expiry
and permission/resource ceilings. Bulk integration revocation is an explicit,
separate action from signing out logins.
