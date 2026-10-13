# Install and manage plugins

Plugins run in BSM's process and can access host resources. Review their source, compatibility and settings before enabling them.

## Install

Place the plugin's Python file or supported package in the plugin directory under the selected data directory. Follow the plugin author's installation instructions for additional dependencies. Use the same Python environment and operating-system account as the manager.

Refresh discovery or restart as appropriate, then inspect the plugin management view. Confirm the plugin's internal name, version and status before enabling it. A discovered plugin is not necessarily enabled.

## Configure and reload

Change the plugin's declared settings through the management interface. Enable or disable it deliberately, then check logs for initialization or cleanup failures. Reload unloads the old instance before loading a replacement; it is not a way to bypass outstanding callbacks.

If unload cannot drain synchronous work, replacement loading can remain blocked until that work finishes. Investigate the callback and avoid repeated reload attempts. Custom router availability follows plugin lifecycle; plugin authors must unregister resources on unload.

See [bundled plugins](../features/default_plugins.md) for built-in behavior and the [author guide](../developer/plugins/introduction.md) for APIs, event ownership and lifecycle responsibilities.
