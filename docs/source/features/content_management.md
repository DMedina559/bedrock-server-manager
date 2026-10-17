# Worlds and addons

Create a [backup](backups.md) before replacing a world, resetting it or changing packs. Content operations can replace gameplay data; inspect task completion and logs before returning the server to players.

## Import and export worlds

Place a `.mcworld` file in the configured world-content library, or use the enabled content-uploader plugin. Select it for the intended server through the content view. Import replaces the active world. Archive validation/extraction failure preserves the existing world.

Export packages the active world as a `.mcworld` file in the world-content library. Confirm the exported file exists before copying or deleting source data.

Reset removes the active world; it does not mean deleting every world belonging to every server. Bedrock creates the replacement on the next start using the configured world properties. Save anything you want to keep first.

## Install and manage addons

Place `.mcpack` or `.mcaddon` files in the addon-content library and select them for installation. Packs must be compatible with your Bedrock version and world. Some features require Bedrock experiment settings.

```{figure} ../../images/web_install_addons.png
:alt: Web interface for installing addons on the selected server
:width: 600px
:align: center

Select an addon from the content library for the intended server.
```

Enabling and disabling packs changes the world's activation lists. Disabled packs can remain installed. Pack ordering follows the stored activation order; test behavior and resource interactions rather than assuming a universal conflict-resolution rule.

```{figure} ../../images/web_manage_installed_addons.png
:alt: Manage Installed Addons dialog showing behavior packs, activation status and ordering controls
:width: 600px
:align: center

Inspect installed behavior and resource packs, adjust their order, and enable or disable them.
```

Removing a pack can affect existing world content. Back up the world, check task results and verify it in-game after restarting. The [manual content guide](../extras/install_content.md) explains file placement when the upload/download plugins are unavailable.

## Choose a subpack

Some resource packs declare multiple subpacks. In **Manage Installed Addons**, open the resource-pack tab and choose an available subpack for the intended pack. Packs without declared subpacks do not offer this selector.

```{figure} ../../images/web_manage_sub_packs.png
:alt: Resource Packs tab showing an installed pack with a subpack selection dropdown
:width: 600px
:align: center

Choose a declared subpack from the installed resource pack's selector.
```
