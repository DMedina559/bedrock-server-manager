# Place content files manually

In addition to uploading archives through the Web UI (`/api/content/upload`), you can place content archives directly in the configured content library on the host filesystem. Resolve its root from application settings; paths need not be relative to your checkout or server directory.

| Library subdirectory | Files |
|---|---|
| `worlds` | `.mcworld` world archives |
| `addons` | `.mcpack` and `.mcaddon` archives |

Copy complete files into the matching library using an account with appropriate permissions. Select the archive through BSM's content management interface; copying it into the library does not install it into a server.

```{figure} ../../images/cli_install_content.png
:alt: Interactive CLI content selection and installation screen
:width: 600px
:align: center

Content can also be selected through the interactive CLI client.
```


Back up the active world before installation and follow the resulting task through completion. See [content management](../features/content_management.md) for replacement effects, export, activation and removal.
