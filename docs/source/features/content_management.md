# Content Management

Bedrock Server Manager allows you to easily manage the content of your server, including uploading new worlds and installing addons (resource and behavior packs).

## World Management

You can import existing worlds, export your current world, or reset the server to a fresh state.

### Importing a World

To use a custom world (e.g., a downloaded map or a backup from another server):

1.  **Upload the World**:
    *   Place your world file (`.mcworld`) into the `content/worlds` directory on the server.
    *   (Enable the content uploader plugin to easily upload content files).
2.  Select the server from the dropdown menu in the web dashboard.
3.  Navigate to the **Extras > Manage Content > Manage World** page from the web dashboard.
4.  Locate the file in the **Available Worlds** list.
5.  Click the **Import** button next to the file.
6.  **Warning**: This action will replace the currently active world on the server. Ensure you have backed up your current world if you wish to save it.

### Exporting the Current World

To save a copy of your current world for download or transfer:

1.  Select the server from the dropdown menu in the web dashboard.
2.  Navigate to the **Extras > Manage Content > Manage World** page from the web dashboard.
3.  Click the **Export World** button.
4.  BSM will compress the active world directory into a `.mcworld` file.
5.  The file will be exported to the `content/worlds` directory for you to import into another server.

### Resetting the World

To start fresh with a newly generated world:

1.  Select the server from the dropdown menu in the web dashboard.
2.  Navigate to the **Extras > Manage Content > Manage World** page from the web dashboard.
3.  Click the **Reset World** button.
4.  Confirm the action.
5.  BSM will delete the current `worlds/` directory.
6.  Upon the next server start, the Bedrock Dedicated Server software will generate a new world based on the `level-seed` defined in `server.properties`.

## Addons (Resource & Behavior Packs)

BSM simplifies the process of installing addons to enhance your server.

### Installing Addons

1.  **Upload the Addon**:
    *   Place your addon file (`.mcpack`/`.mcaddon`) into the `content/addons` directory.
      * *   (Enable the content uploader plugin to easily upload content files).
2.  Select the server from the dropdown menu in the web dashboard.
3.  Navigate to the **Extras > Manage Content > Manage Addon** page from the web dashboard.
4.  Locate the file in the **Available Addons** list.
5.  Click the **Install** button.

### How It Works

When you install an addon, BSM performs the following actions:
1.  **Extraction**: Unzips the package.
2.  **Placement**: Moves resource packs to `resource_packs/` and behavior packs to `behavior_packs/`.
3.  **Activation**: Automatically updates `world_behavior_packs.json`, and `world_resource_packs.json` to register the new content with the server.
