# Accounts, roles and access

BSM authenticates dashboard and API users. Its roles control management access, independently of Minecraft allowlists and player permissions.

| Role | Typical scope |
|---|---|
| User | Authenticated views and permitted account/task operations |
| Moderator | Operational actions such as starting/stopping servers and editing supported player-access files |
| Administrator | Installation, destructive maintenance, users, global settings, plugins and runtime control |

Permissions are attached to individual routes. This table summarizes the roles; it is not a promise that every endpoint in a category has the same policy. Task operations can also depend on task ownership. Consult the running API documentation and route implementation for an integration's exact requirements.

Authentication endpoints and invitation registration have their own public/token-based flows. Plugin endpoints must explicitly apply their required authentication dependencies.

## Manage user accounts and per-server access

Administrators can inspect accounts in **Users**, create invitations, and edit a user's role, active status, and server access policy. Confirm the intended account before saving access changes. Invitation expiry is reported when the invitation is created.

For `user` and `moderator` accounts, administrators can leave server access unrestricted (`all`) or restrict the account to `assigned` servers (`/api/access/users/{user_id}/servers`) with specific per-server permissions (for example, `servers:read` for a `user`, or `servers:read`, `servers:lifecycle`, `servers:command`, and `backups:create` for a `moderator`). Per-server assignments narrow access within the account's role ceiling—they never grant permissions that the account's global role does not already hold (for example, assigning `servers:configure` or `servers:delete` requires the `admin` role). Use the access preview tool (`/api/access/users/{user_id}/servers/preview`) to inspect an account's effective capabilities before saving.

### Role and permission reference

<!-- BEGIN GENERATED PERMISSIONS -->
BSM defines 58 built-in permissions across 25 categories, plus dynamic plugin permissions (`plugin:<plugin_name>:<perm>`). Default role grants remain an upper bound; credentials, server assignments and MFA policy can narrow effective access.

| Permission | Category | `user` | `moderator` | `admin` | Server-scoped? | Delegatable to integration tokens? |
|---|---|---|---|---|---|---|
| `access:manage` | access | — | — | Yes | No | **No** |
| `account:manage` | account | Yes | Yes | Yes | No | **No** |
| `account:read` | account | Yes | Yes | Yes | No | Yes |
| `addons:manage` | addons | — | — | Yes | Yes | Yes |
| `addons:read` | addons | — | Yes | Yes | Yes | Yes |
| `allowlist:manage` | allowlist | — | Yes | Yes | Yes | Yes |
| `allowlist:read` | allowlist | — | Yes | Yes | Yes | Yes |
| `application:logs` | application | — | — | Yes | No | Yes |
| `audit:read` | audit | — | — | Yes | No | Yes |
| `backups:create` | backups | — | Yes | Yes | Yes | Yes |
| `backups:destinations` | backups | — | — | Yes | Yes | Yes |
| `backups:export` | backups | — | — | Yes | Yes | Yes |
| `backups:keys` | backups | — | — | Yes | No | Yes |
| `backups:manage` | backups | — | Yes | Yes | Yes | Yes |
| `backups:prune` | backups | — | Yes | Yes | Yes | Yes |
| `backups:read` | backups | — | Yes | Yes | Yes | Yes |
| `backups:restore` | backups | — | Yes | Yes | Yes | Yes |
| `bans:manage` | bans | — | — | Yes | Yes | Yes |
| `bans:read` | bans | — | — | Yes | Yes | Yes |
| `content:manage` | content | — | — | Yes | Yes | Yes |
| `content:read` | content | — | Yes | Yes | Yes | Yes |
| `diagnostics:read` | diagnostics | — | — | Yes | No | Yes |
| `downloads:prune` | downloads | — | — | Yes | No | Yes |
| `downloads:read` | downloads | — | Yes | Yes | No | Yes |
| `health:read` | health | Yes | Yes | Yes | No | Yes |
| `permissions:manage` | permissions | — | Yes | Yes | Yes | Yes |
| `permissions:read` | permissions | — | Yes | Yes | Yes | Yes |
| `players:manage` | players | — | Yes | Yes | No | Yes |
| `players:read` | players | — | Yes | Yes | No | Yes |
| `plugins:manage` | plugins | — | — | Yes | No | Yes |
| `plugins:pages` | plugins | Yes | Yes | Yes | No | Yes |
| `plugins:read` | plugins | — | — | Yes | No | Yes |
| `properties:manage` | properties | — | Yes | Yes | Yes | Yes |
| `properties:read` | properties | — | Yes | Yes | Yes | Yes |
| `runtime:metrics` | runtime | Yes | Yes | Yes | No | Yes |
| `runtime:read` | runtime | — | — | Yes | No | Yes |
| `runtime:shutdown` | runtime | — | — | Yes | No | Yes |
| `scheduler:manage` | scheduler | — | — | Yes | No | Yes |
| `scheduler:read` | scheduler | — | — | Yes | No | Yes |
| `servers:command` | servers | — | Yes | Yes | Yes | Yes |
| `servers:configure` | servers | — | — | Yes | Yes | Yes |
| `servers:delete` | servers | — | — | Yes | Yes | Yes |
| `servers:inspect` | servers | — | Yes | Yes | Yes | Yes |
| `servers:install` | servers | — | — | Yes | Yes | Yes |
| `servers:lifecycle` | servers | — | Yes | Yes | Yes | Yes |
| `servers:logs` | servers | — | Yes | Yes | Yes | Yes |
| `servers:read` | servers | Yes | Yes | Yes | Yes | Yes |
| `sessions:admin` | sessions | — | — | Yes | No | **No** |
| `sessions:manage` | sessions | Yes | Yes | Yes | No | **No** |
| `settings:manage` | settings | — | — | Yes | No | Yes |
| `settings:read` | settings | — | — | Yes | No | Yes |
| `tasks:read` | tasks | Yes | Yes | Yes | No | Yes |
| `tokens:manage` | tokens | Yes | Yes | Yes | No | **No** |
| `users:manage` | users | — | — | Yes | No | **No** |
| `users:read` | users | — | Yes | Yes | No | Yes |
| `worlds:manage` | worlds | — | — | Yes | Yes | Yes |
| `worlds:read` | worlds | Yes | Yes | Yes | Yes | Yes |
| `worlds:reset` | worlds | — | — | Yes | Yes | Yes |
<!-- END GENERATED PERMISSIONS -->

```{figure} ../../images/web_users_page.png
:alt: User Management listing BSM accounts, assigned roles and active status
:width: 600px
:align: center

The user list shows account roles and whether each account is active.
```

```{figure} ../../images/web_manage_user.png
:alt: Edit User dialog with a BSM role selector and account activation control
:width: 600px
:align: center

Edit the selected account's BSM role and active status.
```

## Your account, MFA, sessions, and integration tokens

Open **Account** to manage your profile, security credentials, and API integrations across five tabs:

- **Sessions:** Inspect active login sessions (`bsm-cli auth sessions`), rename devices, or revoke individual or all other sessions.
- **Integrations:** Create, preview, rotate, and revoke named integration tokens (`bsm_it_...`) scoped to specific permissions, optional assigned servers, and an expiration window.
- **My access:** Inspect your effective role, global permissions, and per-server access grants.
- **Activity:** Review recent account security events (logins, MFA changes, token and session changes).
- **Password & MFA:** Update your password, enroll a TOTP authenticator app with one-use recovery codes, register **WebAuthn Passkeys** for passwordless sign-in and step-up verification, and manage remembered trusted devices. Sensitive account and destructive changes require recent authentication verification (`X-BSM-Recent-Auth: required`, valid for `security.recent_auth_window_minutes`, default 10 minutes).

### Passkeys, TOTP MFA, and trusted devices

- **WebAuthn Passkeys:** Each user can register up to 20 passkeys (`POST /auth/passkeys/register/options` and `/verify`) with user verification required (`uv=required`). Passkeys support direct passwordless sign-in from the login page (`POST /auth/passkeys/login/options` and `/verify`) and satisfy recent-auth step-up prompts (`POST /auth/verify-passkey`). Users who have at least one registered passkey can enable **Require passkey for sign-in** (`passkey_required`) to disable password+TOTP sign-in on their account.
- **TOTP MFA & recovery codes:** Enrolling an authenticator app (`POST /auth/mfa/setup` and `/enable`) generates a 160-bit Base32 TOTP secret (SHA-1, 6 digits, 30-second period) and **10 single-use recovery codes** (`XXXX-XXXX`). Store recovery codes offline; if you lose your authenticator and have no passkey or recovery code, an administrator can clear MFA from **Users** (`POST /api/users/{id}/reset-mfa`) or locally via `bedrock-server-manager reset-mfa --username <user>`. When `security.require_admin_mfa` is enabled in Global Settings, administrator accounts without TOTP or a passkey are restricted to onboarding and account-security routes until MFA is configured.
- **Trusted devices:** Checking **Remember this device for 30 days** during MFA verification registers a hardware-independent device cookie (`bsm_td`) valid for `security.trusted_device_days` (default 30 days, up to 20 trusted devices per user). Manage or revoke trusted devices from **Account → Password & MFA** or `bsm-cli auth devices`.

### Integration tokens (`bsm_it_...`)

Integration tokens allow scripts, CI/CD pipelines, and `bsm-cli auth login --token` to authenticate without interactive cookies or MFA prompts:

- Each user can maintain up to 100 active tokens (`tokens:manage`), and administrators can inspect or revoke any user's tokens (`access:manage`).
- A token's requested scopes cannot include non-delegatable permissions (`tokens:manage`, `access:manage`, `account:manage`, `users:manage`, `sessions:manage`, and `sessions:admin`).
- Effective token permissions are evaluated **live** on every request as the intersection of the token's granted scopes and the owning user's current role and server assignments. If the owning user's role is downgraded, server access is removed, or account is disabled, the token immediately loses that access without needing manual revocation.

### Invitations and password requirements

- **Invitations:** Administrators create single-use registration links (`POST /api/users/invitations`) choosing the invitee's initial role (`user`, `moderator`, or `admin`), optional server assignments, and expiration window (`expires_in_hours`, default 72 hours, from 1 to 168 hours). Unclaimed invitations can be revoked at any time (`DELETE /api/users/invitations/{invite_id}`).
- **Password policy:** Passwords must be between 12 and 128 characters, contain at least 3 of the 4 character classes (uppercase, lowercase, digit, symbol), and not match common weak patterns. Changing a password revokes all other sessions and trusted devices for that account.

### Security audit log

Administrators (`audit:read`) can query the structured security and administrative audit trail in the Web UI (**Audit Log**, `GET /audit-log/list`) or from the CLI (`bsm-cli audit`), filtering by actor ID, action name, target user, or chronological cursor.

Your BSM role describes access to the manager; it does not grant Minecraft operator permissions. See [HTTP permissions and browser authentication](../developer/http_access.md) for full details on scopes, MFA, passkeys, and token policies.

```{figure} ../../images/web_account_page.png
:alt: My Account page with profile information and a password-change form
:width: 600px
:align: center

Inspect your own account profile and update your password.
```

## Runtime shutdown

Runtime status requires an administrator. Shutdown accepts administrator authentication or the private per-instance shutdown credential used by the local CLI. That credential grants shutdown only and must be protected with the configuration directory. See [runtime control](../extras/web_runtime.md).

## Grant access deliberately

Give each person their own account and the minimum role needed for their work. Review invitation expiry and account access when responsibilities change. Changing a BSM role does not change a player's Bedrock operator status.
