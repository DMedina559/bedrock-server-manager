# First startup

[Install BSM](../extras/installation.md), activate its Python environment, and start the web host:

```sh
bedrock-server-manager web start --host 127.0.0.1 --port 11325
```

Open `http://127.0.0.1:11325`. Complete the initial account setup presented by your installation, then sign in. Keep the host running while using the dashboard.

```{figure} ../../images/web_first_time_setup.png
:alt: Initial setup form for creating the BSM administrator account
:width: 600px
:align: center

Create the initial administrator account before signing in.
```

## Create your first server

1. Create a server with a unique name and choose the Bedrock release to install.
2. Review its properties, including game ports and access settings.
3. Start it and inspect status and logs before connecting from Minecraft Bedrock.
4. Create a world backup after confirming the installation works.

The web port serves BSM. Minecraft connects to the Bedrock server's configured UDP game port. Give each simultaneously running server distinct ports and allow those ports through the host firewall.

## Make startup persistent

Run BSM under a [service or container](../extras/web_runtime.md) when it must survive a terminal closing. Use the same configuration directory and operating-system account as your manual installation. Changing accounts or directories can appear to create a fresh installation.

Before exposing BSM beyond the machine, review [access and roles](../web/role_access_table.md) and [proxy configuration](../extras/web_extras.md).

Next: [manage servers](../features/server_management.md), [back up worlds](../features/backups.md), or [troubleshoot startup](troubleshooting.md).
