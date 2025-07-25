# Introduction to Plugins

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg
:alt: Bedrock Server Manager Logo
:width: 150px
:align: center
```

This guide explains how to manage and create plugins to extend and customize the Bedrock Server Manager. Plugins can add new features, notifications, and automation to your server management workflow.

---

## How Plugins Work

Plugins are small Python scripts that "hook into" the Bedrock Server Manager to add functionality. You don't need to know how to code to use them. You can simply download a plugin and activate it.

### Finding Plugins

1.  **Locate the `plugins` directory:** Find the application's data directory. Inside, there will be a `plugins` folder. If it doesn't exist, the application will create it on its first run.
2.  **Install a plugin:** To install a new plugin, simply place its Python file (e.g., `some_plugin.py`) inside this `plugins` directory.

---

## Managing Plugins with the Command Line

You can easily control which plugins are active using the `bedrock-server-manager plugin` command-line interface (CLI).

*   **`bedrock-server-manager plugin list`**
    *   Displays all discovered plugins and their current status (Enabled/Disabled).
    *   **Example:**
        ```
        $ bedrock-server-manager plugin list
        Fetching plugin statuses...
        Plugin Statuses:
        Plugin Name                         | Status   | Version |
        ------------------------------------|----------|---------|
        server_lifecycle__notifications     | Enabled  | 1.0.0   |
        my_custom_plugin                    | Disabled | 1.4.5   |
        ```

*   **`bedrock-server-manager plugin enable <plugin_name>`**
    *   Enables the specified plugin. The name is the filename without `.py`.
    *   **Example:** `bedrock-server-manager plugin enable my_custom_plugin`

*   **`bedrock-server-manager plugin disable <plugin_name>`**
    *   Disables a plugin you no longer want to use.
    *   **Example:** `bedrock-server-manager plugin disable server_lifecycle_notifications`

Changes made with these commands are saved immediately and will be applied the next time the application starts.

---

## The `plugins.json` Configuration File

Plugin statuses, versions, and descriptions are stored in a file named `plugins.json`.

*   **Location:** This file is located in your application's configuration directory (typically `~/.bedrock-server-manager/.config/plugins.json`).
*   **Functionality:** It stores a list of all known plugins and whether they are enabled (`true`) or disabled (`false`), their version, and description.
*   **Discovery:** When the application starts, it scans the `plugins` directory. Any new `.py` files found will be automatically added to this file as `disabled`. You can then enable them using the `plugin enable` command or through the web ui.

### Default Plugins
A few essential built-in plugins are included in BSM to provide core functionality. You can enable/disable them if you wish. The current list includes:
*   `server_lifecycle_notifications` (enabled by default)
*   `world_operation_notifications` (enabled by default)
*   `auto_reload_config` (enabled by default)
*   `update_before_start` (enabled by default)
*   `backup_on_start` (disabled by default)
*   `content_uploader_plugin` (disabled by default)

---

## Creating Your Own Plugins
Check out the [Plugin Developer Guide](../developer/plugins/introduction.md) for detailed instructions on how to create your own plugins. This guide covers everything from using the `PluginBase` class to using event hooks, and the plugin API.