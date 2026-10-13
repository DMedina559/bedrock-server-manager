# Configure a Bedrock server

BSM manages `server.properties`, `allowlist.json` and `permissions.json` for each game server. These files configure Bedrock; they are separate from BSM's [application settings](settings.md) and account roles.

## Properties

Select a server, edit its properties and save. Review port assignments when running multiple servers. Most properties take effect after restarting the game server; saving a file alone does not guarantee the running process has applied it.

Keep a configuration backup before broad changes. For the meanings and supported values of Bedrock properties, use documentation for your installed Bedrock release.

## Allowlist

Set `allow-list=true` in properties when restricting admission to listed players. Add or remove gamertags through the allowlist view. The ignore-player-limit option affects a listed player's admission when the server is full; it does not assign operator permissions.

## Player permissions

Assign Bedrock visitor, member or operator permissions to the intended player identity. BSM's player records and scanned identities help select players; Minecraft permissions do not grant access to the BSM dashboard.

The configuration-reload plugin can apply supported access-file changes to a running server. Check whether it is enabled; otherwise restart the game server when needed. Verify the effective result from the game rather than assuming every file change reloads automatically.
