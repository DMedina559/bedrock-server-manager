# Accounts, roles and access

BSM authenticates dashboard and API users. Its roles control management access, independently of Minecraft allowlists and player permissions.

| Role | Typical scope |
|---|---|
| User | Authenticated views and permitted account/task operations |
| Moderator | Operational actions such as starting/stopping servers and editing supported player-access files |
| Administrator | Installation, destructive maintenance, users, global settings, plugins and runtime control |

Permissions are attached to individual routes. This table summarizes the roles; it is not a promise that every endpoint in a category has the same policy. Task operations can also depend on task ownership. Consult the running API documentation and route implementation for an integration's exact requirements.

Authentication endpoints and invitation registration have their own public/token-based flows. Plugin endpoints must explicitly apply their required authentication dependencies.

## Runtime shutdown

Runtime status requires an administrator. Shutdown accepts administrator authentication or the private per-instance shutdown credential used by the local CLI. That credential grants shutdown only and must be protected with the configuration directory. See [runtime control](../extras/web_runtime.md).

## Grant access deliberately

Give each person their own account and the minimum role needed for their work. Review invitation expiry and account access when responsibilities change. Changing a BSM role does not change a player's Bedrock operator status.
