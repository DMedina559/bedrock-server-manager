# Web Server

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg
:alt: Bedrock Server Manager Icon
:width: 200px
:align: center
```

## Themes
The Bedrock Server Manager web UI supports theming, allowing you to customize the look and feel of the application.

See the [**Theming**](../web/theming.md) documentation for more information on how to create and apply custom themes.

## Custom Web Server Panorama

You can personalize the background panorama displayed on the main web server page.

**Steps:**

1.  Choose your desired background image. It **must** be a JPEG file (with a `.jpeg` extension).
2.  Navigate to the Bedrock Server Manager's configuration directory, typically located at `./.config/` relative to the manager's installation path.
3.  Place your chosen image file into this `./.config/` directory.
4.  Rename the image file to `panorama.jpeg`.
5.  Refresh the web server page in your browser. The new panorama should now be displayed.

**Default Behavior:**

If the file `./.config/panorama.jpeg` is not found or is not a valid JPEG image, the default Bedrock Server Manager icon will be used as the background panorama.

---

## World Icons

The "Servers List" within the web interface can display unique icons for each of your Minecraft worlds, making them easier to identify at a glance.

**How it Works:**

The server manager looks for a file named `world_icon.jpeg` inside each world's specific folder.

**Adding Icons:**

*   **Imported Worlds / Client-Created Worlds:** Worlds that were imported or originally created using the Minecraft client (Bedrock Edition) often already include a `world_icon.jpeg` file within their folder structure. No extra steps may be needed.
*   **Dedicated Server-Created Worlds:** Worlds generated directly by the Bedrock Dedicated Server software usually *do not* have this icon file by default. You can add one manually:
    1.  Obtain or create an image you want to use as the icon (JPEG format, `.jpeg`). A square aspect ratio often looks best.
    2.  Locate the specific world folder for the server you want to customize. This is typically found within the server's directory structure (e.g., `./servers/your_server_name/worlds/your_world_name/`).
    3.  Copy your chosen image file into this specific world folder.
    4.  Rename the image file exactly to `world_icon.jpeg`.
    5.  The icon should appear the next time the server list is loaded or refreshed in the web interface.

**Default Behavior:**

If a `world_icon.jpeg` file is not found within a specific world's directory, the default Bedrock Server Manager icon will be displayed for that world in the server list.

## API Client

The `bsm-api-client` is an asynchronous Python library for interacting with the Bedrock Server Manager API.

This library allows developers to programmatically manage their Minecraft Bedrock servers. It is ideal for automating administrative tasks, building custom control panels, or integrating BSM into other systems and workflows.

It also provides a Command-Line Interface (CLI), allowing you to execute commands on the BSM web server from a local or remote machine.

- **Repository**: [https://github.com/DMedina559/bsm-api-client](https://github.com/DMedina559/bsm-api-client)

## Home Assistant Integration

The Bedrock Server Manager integration for Home Assistant allows you to control and monitor your server directly from your Home Assistant dashboard.

This integration is built using the `bsm-api-client`.

- **Repository**: [https://github.com/DMedina559/bsm-home-assistant-integration](https://github.com/DMedina559/bsm-home-assistant-integration)