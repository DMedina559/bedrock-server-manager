# Worlds and addons

Create a [backup](backups.md) before replacing a world, resetting it or changing packs. Content operations can replace gameplay data; inspect task completion and logs before returning the server to players.

## Import and export worlds

Upload a `.mcworld` file through the Web UI content library (`POST /api/content/upload`) or place it directly in the configured `worlds` content directory. Select it for the intended server through the content view. Import replaces the active world. Archive validation/extraction failure preserves the existing world.

Export packages the active world as a `.mcworld` file in the world-content library, where it can be downloaded through the Web UI (`GET /api/content/worlds/{filename}/download`). Confirm the exported file exists before copying or deleting source data.

Reset removes the active world; it does not mean deleting every world belonging to every server. Bedrock creates the replacement on the next start using the configured world properties. Save anything you want to keep first.

## Install and manage addons

Upload `.mcpack` or `.mcaddon` files through the Web UI or place them in the `addons` content library, then select them for installation. Packs must be compatible with your Bedrock version and world. Some features require Bedrock experiment settings.

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

Removing a pack can affect existing world content. Back up the world, check task results and verify it in-game after restarting. The [manual content guide](../extras/install_content.md) explains direct filesystem placement in the content library.

## Choose a subpack

Some resource packs declare multiple subpacks. In **Manage Installed Addons**, open the resource-pack tab and choose an available subpack for the intended pack. Packs without declared subpacks do not offer this selector.

```{figure} ../../images/web_manage_sub_packs.png
:alt: Resource Packs tab showing an installed pack with a subpack selection dropdown
:width: 600px
:align: center

Choose a declared subpack from the installed resource pack's selector.
```

## Content library management, icons, and archive safety

Manage staged files in `<data_dir>/content/worlds/` and `<data_dir>/content/addons/` through the **Content Library** page or API:

- **List & download:** List staged worlds (`GET /api/content/worlds`) and addons (`GET /api/content/addons`), or download staged files (`GET /api/content/worlds/{filename}/download` and `GET /api/content/addons/{filename}/download`, requires `content:download`).
- **Upload:** Upload `.mcworld`, `.mcpack`, `.mcaddon`, or `.zip` packages (`POST /api/content/upload`, requires `content:upload`). Passing `overwrite=true` replaces an existing file of the same name; otherwise conflicts return `409 Conflict`.
- **Delete:** Remove staged files from the content library (`DELETE /api/content/{category}/{filename}` where `category` is `worlds` or `addons`, requires `content:delete`).
- **World & addon icons:** Authenticated endpoints serve the active world's icon (`GET /api/server/{server_name}/world/icon`, fallback `/image/icon.png`) and installed pack icons (`GET /api/server/{server_name}/addons/{pack_type}/{pack_uuid}/icon`).
- **Archive & filename validation:** Filenames are restricted to `[a-zA-Z0-9_.\- ()\[\]]+` (up to 200 characters) with no leading dot or trailing space/dot. Uploaded archives are inspected before extraction to reject path traversal, absolute paths, symlinks, encrypted ZIP entries, nested ZIP bombs, excessive entry counts (>100,000 entries), excessive expansion (>10 GiB), or extreme compression ratios.
