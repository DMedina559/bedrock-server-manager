# Install Content

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg
:alt: Bedrock Server Manager Icon
:width: 200px
:align: center
```

Easily import addons and worlds into your servers. The app will look in the configured `CONTENT_DIR` directories for addon files.

<div style="text-align: left;">
    <img src="https://raw.githubusercontent.com/DMedina559/bedrock-server-manager/main/docs/images/cli_install_content.png" alt="Install Worlds" width="300" height="200">
</div>

Place .mcworld files in `CONTENT_DIR/worlds` or .mcpack/.mcaddon files in `CONTENT_DIR/addons`

Use the interactive menu to choose which file to install or use the command:

```bash
bedrock-server-manager world install --server server_name --file '/path/to/WORLD.mcworld'
```

```bash
bedrock-server-manager install-addon --server server_name --file '/path/to/ADDON.mcpack'
```