# Accounts, roles and access

BSM authenticates dashboard and API users. Its roles control management access, independently of Minecraft allowlists and player permissions.

| Role | Typical scope |
|---|---|
| User | Authenticated views and permitted account/task operations |
| Moderator | Operational actions such as starting/stopping servers and editing supported player-access files |
| Administrator | Installation, destructive maintenance, users, global settings, plugins and runtime control |

Permissions are attached to individual routes. This table summarizes the roles; it is not a promise that every endpoint in a category has the same policy. Task operations can also depend on task ownership. Consult the running API documentation and route implementation for an integration's exact requirements.

Authentication endpoints and invitation registration have their own public/token-based flows. Plugin endpoints must explicitly apply their required authentication dependencies.

## Manage user accounts

Administrators can inspect accounts in **Users**, create invitations, and edit a user's role or active status. Confirm the intended account before saving access changes. Invitation expiry is reported when the invitation is created.

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

## Your account

Open **Account** to inspect your profile and change your password using the current-password and confirmation fields. Your BSM role describes access to the manager; it does not grant Minecraft operator permissions.

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
