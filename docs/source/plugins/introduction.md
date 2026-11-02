# Install and manage plugins

Plugins run in BSM's process and can access host resources. Review their source, compatibility and settings before enabling them.

## Install

Place the plugin's Python file (`<plugin_name>.py`) or package directory (`<plugin_name>/__init__.py`) in `<data_dir>/plugins/` (configurable via `paths.plugins`). Follow the plugin author's installation instructions for any third-party Python packages, installing them into the same Python environment and OS account as BSM.

* **Discovery rules:** BSM scans `<data_dir>/plugins/` (plus its own bundled plugins). Files or folders starting with `_` or `.`, symlinked plugin entries that fail path checks, classes without a valid `version` attribute, and the reserved directory names `public`, `shared`, and `private` are ignored.
* **Code vs. persistent data:** Plugin source code lives in `<data_dir>/plugins/`. Runtime plugin state lives separately in the database (`plugin_settings` table and `plugins.json` registry) and under `<config_dir>/plugins/<plugin_name>/` (private plugin files) or `<config_dir>/plugins/public/` (shared plugin files).

Refresh discovery (**Reload Plugins** in the Web UI or `PUT /api/plugins/reload`) or restart the manager, then inspect the **Manage Plugins** view. Confirm the plugin's internal name, version, and status before enabling it. Newly discovered third-party plugins start disabled until you enable them.

```{figure} ../../images/web_manage_plugins.png
:alt: Plugin Management showing plugin cards, loaded status, filtering and reload controls
:width: 600px
:align: center

Inspect discovered plugins and their status before changing which plugins are enabled.
```

## Configure and reload

Change the plugin's declared settings through the management interface. Enable or disable it deliberately, then check logs for initialization or cleanup failures. Reload unloads the old instance before loading a replacement; it is not a way to bypass outstanding callbacks.

```{figure} ../../images/web_plugin_settings.png
:alt: Plugin Settings with per-plugin tabs and server lifecycle notification options
:width: 600px
:align: center

Select a plugin tab to inspect and save its declared settings.
```

If unload cannot drain synchronous work, replacement loading can remain blocked until that work finishes. Investigate the callback and avoid repeated reload attempts. Custom router availability follows plugin lifecycle; plugin authors must unregister resources on unload.

See [bundled plugins](../features/default_plugins.md) for built-in behavior and the [author guide](../developer/plugins/introduction.md) for APIs, event ownership and lifecycle responsibilities.

## Repository examples

The repository's `plugins/ping_plugin.py` and `pong_plugin.py` demonstrate typed,
owned custom events. Enable ping before pong. The event-sender example exposes
only its own declared message event and requires administrator authentication.


## Settings scopes

Plugins may declare independent Pydantic models for their own settings, manager-wide settings, and per-server settings. Configure plugin-local values on **Plugin Settings**, global values under **Global Settings → Plugins**, and server values on **Server Settings**. Only plugins declaring a model for a scope appear in its editor. Server settings apply independently to each server.

Defaults appear without writing to the database. Saving validates the complete namespace before committing. A disabled plugin's schema remains available while it is installed; uninstalling a plugin does not silently discard its saved values.
