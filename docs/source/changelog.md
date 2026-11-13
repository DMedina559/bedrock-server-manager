# Changelog

## Unreleased: scope standardization

- Renamed beta scopes: `logs:read` → `servers:logs`, and
  `logs:read_application` → `application:logs`. Recreate affected integration
  tokens and update explicit plugin declarations; there are no compatibility aliases.
- Unknown explicit plugin scopes now prevent that plugin from loading. Plugins
  omitting declarations retain legacy compatibility; an empty list grants no capabilities.
- Global/server plugin settings reads and writes require the corresponding
  `settings:read/manage` or `servers:read/configure` capability. Own plugin-local
  settings remain owner-scoped.
- Installation-wide event diagnostics and operation activity require `diagnostics:read`.
  Current-event and current-sequence coordination remain available without it.
- Scheduler management delegates application-owned automation, including commands,
  updates, resets and maintenance—not just the token's other capabilities.
- Permission documentation is generated from the canonical capability catalog.

```{image} https://raw.githubusercontent.com/DMedina559/bsm-frontend/main/frontend/public/image/icon/web-app-manifest-512x512.png
:alt: Bedrock Server Manager Icon
:width: 200px
:align: center
```


```{changelog}
:changelog-url: https://bedrock-server-manager.readthedocs.io/en/latest/changelog.html
:github: https://github.com/DMedina559/bedrock-server-manager/releases/
:pypi: https://pypi.org/project/bedrock-server-manager/
```
