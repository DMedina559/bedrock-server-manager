# Configure a Bedrock server

BSM manages `server.properties`, `allowlist.json` and `permissions.json` for each game server. These files configure Bedrock; they are separate from BSM's [application settings](settings.md) and account roles.

## Properties

Select a server, edit its properties and save. Review port assignments when running multiple servers. Most properties take effect after restarting the game server; saving a file alone does not guarantee the running process has applied it.

```{figure} ../../images/web_configure_properties.png
:alt: Bedrock Server Properties editor with grouped settings, filtering and Save Changes
:width: 600px
:align: center

Filter and edit the selected server's Bedrock properties, then save the changes.
```

Keep a configuration backup before broad changes. For the meanings and supported values of Bedrock properties, use documentation for your installed Bedrock release.

## Allowlist

Set `allow-list=true` in properties when restricting admission to listed players. Add or remove gamertags through the allowlist view. The ignore-player-limit option affects a listed player's admission when the server is full; it does not assign operator permissions.

```{figure} ../../images/web_configure_allowlist.png
:alt: Server access control interface for managing the allowlist
:width: 600px
:align: center

Manage the selected server's allowlist through Access Control.
```

## Player permissions

Assign Bedrock visitor, member or operator permissions to the intended player identity. BSM's player records and scanned identities help select players; Minecraft permissions do not grant access to the BSM dashboard.

```{figure} ../../images/web_server_permissions.png
:alt: Access Control Permissions tab showing Bedrock member and operator assignments
:width: 600px
:align: center

Assign Bedrock player permissions separately from BSM account roles.
```

The configuration-reload plugin can apply supported access-file changes to a running server. Check whether it is enabled; otherwise restart the game server when needed. Verify the effective result from the game rather than assuming every file change reloads automatically.

## Server bans

Use **Access Control → Bans** to review the selected server's stored bans, add a player ban with an optional reason, or remove an existing entry. Check the intended player identity before changing access. For actions against a connected player, see [online player management](server_management.md#online-players).

```{figure} ../../images/web_manage_server_bans.png
:alt: Access Control Bans tab with player identity, optional reason and stored ban entries
:width: 600px
:align: center

Review and manage bans for the selected server.
```
