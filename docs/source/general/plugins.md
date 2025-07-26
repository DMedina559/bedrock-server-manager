# Plugin Support

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg
:alt: Bedrock Server Manager Icon
:width: 200px
:align: center
```

Bedrock Server Manager 3.4.0 features a powerful plugin system that allows you to extend and customize its functionality. Whether you want to add new automations, integrate with other services, or introduce custom server management logic, plugins provide the framework to do so.

**Key Capabilities:**

*   **Event Hooks:** Plugins can "listen" to various events within BSM (e.g., before a server starts, after a backup completes) and execute custom code in response.
*   **API Access:** Plugins have safe access to core BSM functions, allowing them to perform actions like starting/stopping servers, sending commands, and more.
*   **Custom Events:** Plugins can define and trigger their own events, enabling complex communication and collaboration between different plugins.

**Managing Plugins:**

You can manage your plugins directly from the Web Server:

- Enable/Disable Plugins
- Reload Plugins
- View Plugin Information such as version


**Developing Plugins:**

To learn how to create your own plugins, please refer to the comprehensive:

**[Plugin Documentation](../plugins/introduction.md)**

This documentation covers everything from creating your first plugin, understanding the [`PluginBase`](../developer/plugins/plugin_base.rst) class, using event hooks and the plugin API, to advanced topics like custom inter-plugin events.
