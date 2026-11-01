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

The helpers `get_current_user`, `get_moderator_user`, `get_admin_user`, and
`require_permissions` are exported from `bedrock_server_manager`.

A plugin may declare custom HTTP permissions on `PluginBase`:

```python
class ExamplePlugin(PluginBase):
    version = "1.0.0"
    http_permissions = [
        ("jobs:run", "Run example jobs", ["moderator", "admin"]),
    ]
```

Omitting `plugin:` automatically prefixes `plugin:<plugin_name>:` (for example
`plugin:example:jobs:run`). Use it in a route with `Security(require_permissions,
scopes=["plugin:example:jobs:run"])`. Names must use the plugin's own namespace.
Descriptions and explicit role grants are required; collisions and invalid names
are rejected. Registration is owned by the plugin, removed on unload or failed
load, and invalidates OpenAPI. Admin has no implicit bypass for plugin grants.
This does not change trusted in-process Python plugin access. (The legacy
`self.api.runtime.register_http_permission()` method remains supported for
compatibility but logs a deprecation warning.)

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
Back up the database together with `credentials/mfa.key` (relative to the
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

Integration credential creation accepts `expires_in_days: null` for **Never
expire**; omitting it still defaults to 30 days. Metadata returns
`expires_at: null`. Such credentials remain subject to revocation, account
activation, current role/server access, and the active-credential limit. Rotation
preserves the lack of an expiration deadline. Downgrading to a release without
this capability expires non-expiring credentials at the downgrade time.
Interactive login-session deadlines are unchanged.

The login screen asks for username/password first. Only after those credentials
are verified does an MFA-enabled account receive a 401 with
`X-BSM-MFA: required`; this response issues no session or token. The client then
asks for an authenticator or recovery code and resubmits the credentials with
`otp`. Incorrect passwords never expose whether the account has MFA. API clients
may still supply all three values in a single request.

## Authentication hardening

New and reset passwords require at least 8 characters, reject a local list of
common passwords and highly repetitive values, and accept up to 1024 UTF-8 bytes.
Existing passwords still work at login. New hashes use Argon2id; successful legacy
bcrypt logins upgrade their hash without signing out existing sessions. Unknown
accounts perform dummy password verification. Validation errors omit passwords.

MFA and account authority changes advance the authentication revision so an
in-flight login or verification cannot bypass the change. Role and activation
changes revoke login sessions before advisory connection cleanup. Idle-expired
sessions do not consume the active-session limit. Authentication attempts clean
up old throttle rows and session/security history older than 90 days. Successful
recent verification resets its account attempt budget.

Administrators can configure `security.auth_account_attempts` (default 10),
`security.auth_peer_attempts` (60), and `security.auth_window_seconds` (300).
`security.require_admin_mfa` defaults to false. When enabled, an unenrolled
administrator can only access account enrollment and sign-out until MFA is
confirmed. Named integration credentials keep their independent authorization.
Required administrators cannot disable their own MFA. For a lost factor, an
operator with local configuration/database access can run `bedrock-server-manager
reset-mfa USER` (or add `--yes`); this clears factors, revokes login sessions, and
records the recovery action, without changing the password or integrations.

Owned security changes produce safe, account-scoped notices for connected
interactive clients and the private `on_account_security` core event. Notices
contain an event ID, owner ID, action, and timestamp, never credentials or factor
secrets. Delivery is advisory; the security activity log remains authoritative.

### Registration invitation storage and concurrency

Registration invitations are stored as SHA-256 digests. Existing invitation URLs
remain valid after the digest migration, retain their role and deadline, and can
be redeemed only once. Registration and validation requests share the configured
peer authentication budget. A throttled registration returns 429 before password
hashing or invitation consumption; invalid/expired invitations are also rejected
before hashing. Account creation revalidates the invitation within its transaction.

On PostgreSQL/MySQL, invitation consumption requests a row lock with
`SELECT FOR UPDATE`. SQLite ignores that clause. The supported SQLite application
process serializes account creation with `Storage.write_lock`, including the
invitation recheck, account insert and invitation deletion in one transaction.
That in-process lock is not a cross-worker/distributed lock: do not run independent
BSM application workers against the same SQLite database. A same-process
concurrency test explicitly coordinates both requests past preliminary validation
and proves that only one account is created.

Migration `g83c712e49a0` hashes existing invitation secrets in place and creates
the unique digest index. Downgrading past `g83c712e49a0` cannot reconstruct raw
invitation secrets: existing invitations become unusable and must be reissued.
Re-upgrading removes the unusable null-token rows; it does not restore old links.
Take a database backup before schema changes, and protect older backups because
they may still contain plaintext invitations.

Invitation page/API responses use `Cache-Control: no-store` and
`Referrer-Policy: no-referrer`, including registration throttling responses. BSM's
application log formatter redacts invitation secrets from page, validation and
submission URLs, including ingress-prefixed paths. Configure reverse-proxy access
logs separately: BSM cannot redact logs written by another service. When serving
the frontend separately, apply equivalent cache/referrer rules on registration
page responses at that frontend host; backend headers do not configure it.

## Authentication maintenance and request ownership

JWT authentication resolves a persisted account, validates its login family and
builds current grants once for that request or WebSocket handshake. The internal
`AuthenticatedSession` carries the resulting identity and authorization; it is
not a cross-request cache. Self-service security endpoints reuse the actor's
owner ID from the request context, while administrator operations still look up
the target account. The permission dependency owns the recent-authentication
check for access mutations. Token creation and rotation retain their separate
recent-authentication checks.

Every subsequent protected request and WebSocket frame checks committed state.
A role change closes the old socket identity. Outgoing WebSocket delivery still
refreshes authorization independently under the send lock and filters the
payload again. An already executing request is not retroactively cancelled.
Password verification remains outside database transactions; session issuance
still checks account activity and the authentication revision after verification.

Login and renewal share the pure lifetime policy: 24 hours without remember-me,
otherwise `web.token_expires_weeks` (four weeks if malformed). Persisted session
maximum and idle limits remain authoritative; renewing never extends a family's
absolute deadline. Invalid/non-finite legacy settings cannot overflow a token.

Application startup owns an `authentication-retention` task in HTTP and other
runtime modes. It runs immediately, daily after success and five minutes after
an observable failure. Each transaction deletes at most 250 rows and yields
between full batches. It removes throttle windows older than one day, security
activity older than 90 days and login families whose absolute expiry is over
90 days old. It never deletes integration credentials, including non-expiring
credentials. General audit-log retention is independent. Login, session creation
and activity reads no longer perform retention deletes. Shutdown cancels and
awaits maintenance before closing the database. SQLite deployments still use the
existing supported process model; this task adds no cross-worker locking promise.

### Reproducible workload measurements

Run `BSM_AUTH_BENCHMARK=1 python -m pytest -s tests/web/test_auth_workload.py` with
the same interpreter, hardware and empty SQLite fixture before and after a change.
The opt-in test records statement, write and transaction counts, elapsed time and
owned write-lock wait time, without recording SQL parameters or credentials.
It covers successful/failed login, an enrolled MFA challenge, JWT and integration
requests, WebSocket receive/reply and delivery, and eight concurrent JWT requests.
Write-lock waits cover the application's owned lock, not database-driver waits;
concurrent wall time includes driver contention. Production database contention
and p95 latency require representative deployment measurements.

An illustrative local run against the registration-hardening parent gave:

| Workload | Statements before → after | Transactions before → after | Writes before → after |
| --- | --- | --- | --- |
| Successful login | 28 → 22 | 16 → 14 | 13 → 8 |
| Failed login | 18 → 13 | 10 → 8 | 8 → 4 |
| MFA challenge | 13 → 9 | 8 → 7 | 6 → 2 |
| JWT request | 5 → 4 | 4 → 3 | 0 → 0 |
| Integration request | 6 → 6 | 2 → 2 | 1 → 1 |
| WebSocket subscribe and reply | 12 → 9 | 8 → 6 | 0 → 0 |
| WebSocket delivery | 6 → 6 | 4 → 4 | 0 → 0 |
| Eight concurrent JWT requests | 40 → 32 | 32 → 24 | 0 → 0 |

These are workload-specific observations, not a fixed query budget or a latency
claim. Fail-closed authorization, revocation and factor replay protection take
priority over reducing any count.

## Trusted clients and browser response policy

Ingress checks the immediate peer against `web.forwarded_allow_ips` before
Uvicorn resolves forwarding headers. Authentication budgets use that resulting
ASGI client address, never a separately parsed `X-Forwarded-For`. Equivalent IPv6
forms and IPv4-mapped IPv6 addresses share a canonical budget. By default,
`security.auth_ipv6_prefix=128` keeps distinct IPv6 clients separate. Operators
may choose a shorter prefix (48–128) to group addresses, accounting for shared
networks; account budgets continue to apply across all addresses. Untrusted
forwarding headers cannot select the ingress path or a different client budget.

Backend responses set `X-Content-Type-Options: nosniff`,
`Permissions-Policy: camera=(), microphone=(), geolocation=()`, and default to
`Referrer-Policy: strict-origin-when-cross-origin`. Invitation routes retain the
stricter `no-referrer` and `no-store` policy. Clipboard and public-key credential
(WebAuthn) features remain enabled.

No frame restriction is imposed by default, preserving cross-origin Home
Assistant embedding. Configure `web.frame_ancestors` with explicit CSP sources,
for example `'self' https://home.example`, to restrict embedding. Setting it to
`'self'` alone prevents a separately hosted Home Assistant from embedding BSM.
No unconditional `X-Frame-Options` header is added.

`web.csp_report_only` optionally sends `Content-Security-Policy-Report-Only`.
Start with reporting, then inspect login, clipboard copy, Swagger's CDN assets,
plugin pages, theme assets, remote-instance HTTP calls and WebSocket connections
under standalone and ingress URLs. Add a suitable reporting endpoint only where
the deployment provides one. This option does not enforce a source policy.
A frontend hosted separately must configure equivalent headers at its own host;
backend headers do not cover standalone HTML. Do not enforce a blanket CSP
without testing the deployment's origins, extensions and embedded integrations.

## Authorization ordering and bounded audit history

Server-scoped routes authorize before checking server registration or installation
files. Anonymous requests return 401; credentials without the capability or server
grant return 403 for both existing and missing private server names. Authorized
callers still receive normal resource-validation errors. World and addon icons
also require authorization (`servers:read` and `content:read` respectively),
including server-grant checks. Embedded cookies work normally; bearer clients
must fetch these binary operations with their credentials and display the
returned image, rather than putting a token in an image URL. The frontend owns
and releases the resulting object URLs on credential/resource changes.

Password change and reset read the account in a short transaction, perform
password verification/hashing outside it, then atomically update only the same
owner, revision and previous hash. Concurrent credential/account changes reject
the stale operation. Session revocation and the security event commit with the
new hash; notifications follow the commit. This policy does not assume every
SQLite transaction is an exclusive write lock or promise a fixed millisecond
transaction budget.

`GET /audit-log/list` keeps its JSON array response and adds optional `limit`
(1–500, default 100) and `offset` (nonnegative, default 0). Ordering is timestamp,
then ID, descending. Continue paging to access older permanent audit records;
retention does not delete them. New entries can shift offsets between requests.
The frontend displays 100 events at a time and uses a bounded extra record to
check whether an older page exists. Python clients expose both query parameters;
`bsm-cli audit --limit 100 --offset 100` reads the next page. Repository callers
can pass the same bounded keyword arguments to `get_all_logs`.

Cookie-authenticated mutations fail closed if their CSRF proof cannot be built.
A missing/invalid cookie does not establish an authenticated identity: protected
routes reject it, and a 401 clears only the selected cookie credential using the
same secure, ingress-aware cookie policy. An invalid explicit bearer credential
never deletes a separate browser cookie. Static asset bypasses match complete
path boundaries, including `/themes`, rather than similarly prefixed endpoints.

MFA enrollment, recovery-code replacement and other sensitive actions still
require recent verification. A 403 carrying `X-BSM-Recent-Auth: required` opens
the identity-verification dialog; after verification, retry the original action.
Ordinary permission/CSRF failures are not treated as a step-up challenge. Browser
`ERR_CONNECTION_REFUSED` errors mean the configured backend is unreachable and
are separate from a five-minute verification expiry.

## Remembered second-factor devices

After a successful authenticator or recovery-code check, an interactive login or
password reauthentication can opt into `remember_device`. This issues a separate,
revocable credential valid for **30 days**. It can replace the OTP check at login
and during five-minute security reauthentication, including recovery-code
replacement. The current password remains required. A remembered credential
cannot authenticate by itself or extend its own expiry; renewal requires a fresh
OTP or recovery code. An explicitly supplied incorrect OTP never falls back to
remembered trust. Remember devices only on browsers or clients you control.

Cookie-mode clients receive the proof in an HttpOnly, SameSite cookie using the
existing HTTPS/ingress cookie policy, scoped per account. Bearer clients receive
`trusted_device_token` and `trusted_device_expires_at` only when a fresh grant is
issued. They must deliberately store the proof as a secret scoped to the backend
and account, then supply it on password login or via
`X-BSM-Trusted-Device-Token` on account-security requests. Bearer login does not
implicitly consume ambient device cookies. Responses are not cacheable. Only a
SHA-256 digest is stored on the server; device listings contain metadata only.

Account Security → Sessions lists remembered devices separately from login
sessions and supports forgetting one, others, or all devices. Forgetting trust
does not sign out a session, but invalidates recent verification derived from that
device. Independent fresh-OTP verification remains valid. Expired or revoked
proofs are checked again at use, rather than cached as authorization decisions.
Password, role, account-status and MFA changes invalidate device grants through
the account security revision. Recovery-code replacement carries forward only
the presented, valid current device with its original expiry and invalidates all
other remembered devices. At most 20 current grants are retained; adding another
replaces the oldest. Old metadata is bounded and expired records are eligible for
the existing background retention process after 90 days.

Migration `g83c712e49a0` adds the trusted-device, passkey, and WebAuthn challenge
tables along with recent-verification provenance. Downgrading removes device and
passkey grants; accounts and passwords remain intact.


## Access previews, retention, and execution boundaries

`POST /api/account/tokens/preview` accepts the same body as credential creation.
It returns `requested_permissions`, `effective_permissions`,
`unavailable_permissions`, `server_permissions` keyed by immutable server ID,
and `policy_revision`. It creates no credential. The preview applies the current
role, account assignments, non-delegatable permissions, and proposed server list.
It can explain an unavailable permission that creation would reject. A preview
is advisory; creation and every authenticated request still enforce current access.

Administrators can preview proposed assignments with
`POST /api/access/users/{user_id}/servers/preview`, using the same body as the
assignment update. This shows which proposed grants the target role can actually
exercise. Saving a grant never raises the account's role ceiling.

Integration credential listings retain their array response and accept `limit`
(default 100, maximum 500) and `offset` (default 0). The same pagination applies
to administrators listing another account's credentials. Rows are ordered by
creation time descending, then ID descending. Offset pages can shift when new
credentials are created. Revoked or expired credentials become eligible for
background removal after 90 days; active non-expiring credentials are retained.
Deleting an account atomically removes its credentials, login sessions, MFA
material, remembered devices and server assignments. Security and administrative
audit events retain their existing history policy. Maintenance also removes
historical orphaned secrets and grants in bounded batches.

HTTP-submitted background work revalidates its credential, effective permissions,
and original server identity immediately before execution, after waiting for a
concurrency slot. Revoked credentials or removed capabilities cancel queued work.
Server deletion and recreation under the same name cannot redirect an accepted
task. Work already executing keeps the operation's existing safe cancellation and
recovery behavior; an access change does not interrupt a restore midway.

Application log history requires `logs:read_application`; server log history
requires `logs:read` for the selected server. This matches socket topic access.
The OpenAPI `x-bsm-access.credential_alternatives` field describes conditional
capabilities and dedicated local credentials. Swagger displays these alternatives;
OAuth security entries carry the capability required for each alternative.

Interactive backup emergency-kit downloads require recent password/factor
verification and use the existing `X-BSM-Recent-Auth` challenge. Integration tokens
remain eligible only when explicitly delegated `backups:keys` with global access;
this capability includes exporting secret recovery credentials. Server-restricted
tokens cannot use global key routes.

All authentication and setup responses use `Cache-Control: no-store` and
`Pragma: no-cache`, including ordinary bearer login and failures. MFA key files
use the same private-path policy as backup credentials: owner-only POSIX modes,
or a protected Windows DACL for the service identity, administrators and SYSTEM.
Existing key files are checked and protected when opened.

## Auth audit follow-ups: management and verification

Integration credential lists accept bounded `limit` (1–500), `offset` and `status`
(`all`, `active`, `inactive`) queries. The API keeps its array response and its
`all` default; the account UI defaults to Active and pages 50 records at a time.
Expired and revoked history is separate, so an old active credential remains
individually discoverable. CLI users can use `auth tokens list --status inactive
--limit 50 --offset 50`. Offset pages may shift during concurrent changes.
Session and remembered-device metadata prioritize active entries before applying
their existing history bounds.

Credential creation and account server-assignment forms show an advisory preview
of effective capabilities, unavailable capabilities, affected servers and policy
revision. Invalidated/obsolete preview requests are aborted. The write always
checks current permissions again; the preview is not a saved authorization grant.
Server-assignment previews are explicitly read-only; saving administrative grants
still requires recent verification. API Explorer displays conditional credential rules,
including server/application logs and dedicated supervisor credentials.

MFA verification reads a versioned factor snapshot in a short transaction, does
key-file protection/read/decryption outside it, then conditionally commits using
the factor version, encrypted secret and active owner's security revision.
Enrollment also rechecks its pending secret and deadline at commit. Concurrent
TOTP or recovery-code use has at most one winner. This deliberately preserves
security checks even if it increases a SQL statement count; it does not promise
an exclusive-write-lock duration or immediate cancellation of already-running work.

New and reset passwords keep the eight-character minimum. The packaged offline
SecLists common-password dataset supplements the local application-specific
rejections. Password checks never send passwords to SecLists or another service.
The dataset, MIT license, immutable upstream commit, entry count and SHA-256 are
under `bedrock_server_manager/data/common-passwords*` and included in distributions.
Maintainers should review the list before security releases and periodically
against upstream. Run `python scripts/update_password_blocklist.py --check` to
verify bundled provenance without network access. To refresh, review upstream
licensing and a specific commit, run the script with `--revision <40-character
commit>`, review the diff, and commit all data/license/provenance files together.
This is a common-password screen, not a complete breached-password database or an
entropy estimate. Existing login passwords are not revalidated against a new list.

Remembered-device events refresh account security views and have fixed, non-secret
notification messages. Revocation records contain the affected device ID/mode and
count; replacement records identify replaced grants. SDK/CLI requests have distinct
client hints, which are descriptive metadata and never proof of hardware identity.
`auth devices list` and `auth devices forget <id>`, `--others` or `--all` manage this
trust independently of login sessions. CLI setup stores the new account label;
remembering reauthentication resolves the authenticated account before saving the
proof. Environment credential overrides do not implicitly reuse a saved owner's
remembered proof. The frontend offers a fresh-authenticator choice for deliberate
renewal; trust alone never renews the original deadline.

Recovery codes can be copied explicitly with inline success/failure feedback and
a manual-selection fallback, alongside file download. Clipboard actions never run
automatically or store codes in notification history. Automated picker/fallback
tests do not certify native Windows Save As behavior: verify save/cancel, slow
destinations and ingress/fallback on the affected Windows/browser installation.

The opt-in workload test now includes successful TOTP/recovery-code login,
remembered-device creation/login/password step-up, invalid/expired/revoked trust,
and mixed concurrent login/reauthentication. `BSM_AUTH_BENCHMARK_SAMPLES` selects
1–5 samples per repeatable workflow (default 3); one-use TOTP/grant setup and socket
cases are measured once. Output includes raw count/timing samples and diagnostic
median/p95 summaries, never credentials or SQL parameters. Small-sample quantiles
are not production p95 estimates. The fixture raises only its own test throttle
budgets. SQLite is measured here; PostgreSQL/MySQL deployments require their own
representative driver, contention and isolation measurements before making
cross-process/concurrency claims.

## Router audit follow-up, passkeys, and host credentials

Host secret credentials live in `<config_dir>/credentials/` using the `.key`
extension (`backup.key`, `jwt.key`, and `mfa.key`), separate from application
settings. Each file and the containing directory use owner-only POSIX permissions
or protected Windows ACLs. Private-path symlinks are rejected. The initial JWT
signing key file (`<config_dir>/credentials/jwt.key`) is published atomically
under an OS-held lock. An initialized host with a missing, corrupt, or unreadable
key fails clearly; it never silently rotates the key. The validated key is retained
in the owning Settings instance for the process lifetime; replacing files is not
a supported live key-rotation interface.

Keep `<config_dir>/credentials/` with the configuration volume when moving or
recovering an installation. Server backup archives do not carry installation JWT
or MFA keys. Restoring just the database does not restore host credentials. Stop
the application before restoring a matching database/configuration pair. Generic
settings writes cannot change the signing key or its initialization marker, and
HTTP settings reads/forms never expose either field.

### WebAuthn passkeys

Accounts can register up to 20 active WebAuthn passkeys (`POST /api/account/security/passkeys/register/options`
and `POST /api/account/security/passkeys/register/verify`) after recent step-up
verification. Passkeys support:

- **Passwordless sign-in** (`POST /auth/passkey/options` and `POST /auth/passkey/verify`,
  operation IDs `begin_passkey_login` and `complete_passkey_login`) with
  `userVerification="required"`, satisfying both primary and second-factor
  requirements (including `security.require_admin_mfa`) when the authenticator
  asserts `UV`.
- **Step-up reauthentication** (`POST /api/account/security/passkeys/verify/options`
  and `POST /api/account/security/passkeys/verify`, operation IDs
  `begin_passkey_step_up` and `verify_account_security_passkey`) for five-minute
  sensitive account/admin operations.
- **Self-service and admin management**: users can list (`list_passkeys`), rename
  (`rename_passkey`), and revoke (`revoke_passkey`) their own passkeys;
  administrators can inspect another user's passkeys (`list_account_passkeys` at
  `GET /api/access/users/{user_id}/passkeys`) and clear them as part of
  `reset_account_mfa`.

Settings authorization follows the setting's storage scope, including fields
introduced by plugins:

| Scope | Read | Write |
| --- | --- | --- |
| Plugin-owned settings table | `plugins:read` | `plugins:manage` |
| Installation/global settings and `custom.<plugin>` | `settings:read` | `settings:manage` |
| Server settings and `custom.<plugin>` | `servers:read` for that server | `servers:configure` for that server |

Generic global HTTP settings exclude the separate plugin-settings table and reject
writes to that table, including legacy aliases. Plugin-owned values remain available
through the plugin endpoint. Scoped plugin GET/PUT endpoints use the same permissions
as their corresponding global/server settings; selecting a server never bypasses
its assignment or token boundary. Plugin-defined server/global namespaces are not
classified as private merely because a plugin declares them. Plugins must not place
secret credentials into an ordinary readable field; use protected plugin files or
an explicitly designed secret-field interface when confidentiality is required.

Addon inventory reads use `content:read`, while mutations retain `content:manage`.
Read-only inventory consumers receive icon availability without absolute host paths;
existing management consumers retain their full inventory. Bundled global content
uploads require `content:manage`; bundled download pages/files select `backups:read`
with server checks or global `content:read` according to their validated request.
The development event-sender and dynamic-page plugins require `plugins:manage`.
Legacy third-party role dependencies retain their compatibility behavior.

All core tags are declared in the central catalog. Access metadata includes recent
verification and ownership conditions; administrative advisory previews are explicitly
marked read-only and do not consume mutation step-up. Actual mutations still require
recent verification. Plugin registration preflights duplicate operation IDs and
normalized method/path bindings before mounting; existing generated plugin IDs are
frozen verbatim, and new IDs should use stable namespaced snake_case. The legacy
GET logout operation remains hidden and unchanged. Registration/logout/key-info and
panorama responses have concrete success or binary content declarations. Client
contracts are regenerated without renaming existing core operation IDs.

### Passkey proof and concurrency guarantees

Passkey registration, passwordless login, and passkey step-up request and verify
user verification (PIN/biometric). A presence-only assertion cannot replace a
password or satisfy administrator MFA. Accounts with passkeys but no authenticator
app must use their passkey for sign-in and sensitive verification; password-only
attempts return `X-BSM-MFA: passkey`. Accounts with TOTP retain password plus
OTP/recovery-code/remembered-device authentication.

Enrolling a passkey signs out other sessions, retaining the enrolling session.
Revocation invalidates in-flight factor proofs and recent-verification grants,
without automatically revoking unrelated established sessions. Challenges are
consumed by a conditional database write; concurrent zero-counter assertions
cannot reuse a challenge. Session creation and step-up recheck the proof at the
write boundary. Secret-free login activity records the authentication method.

Auth request bodies are bounded to 64 KiB before parsing, including chunked
requests. Encoded WebAuthn fields and RSA/signature sizes are bounded, and
verification uses a limited worker pool. Passkey orchestration lives in
`services/passkey_service.py`; persisted session lifecycle remains in
`services/session_service.py`. Existing HTTP operation IDs are unchanged.

Session rows persist the authentication method and whether a second factor was
verified (defaulting to `unknown` and `false` rather than assuming proof from
current enrollment). An unverified session on an account with an enrolled factor
must sign in again; unaffected password-only accounts and named integration
credentials keep their existing behavior.
