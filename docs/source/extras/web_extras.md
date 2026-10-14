# Hosting and web customization

Bind the web host to an address appropriate for its exposure. The default loopback binding is accessible from the local machine; a broader binding can expose BSM to other hosts.

## Reverse proxies

When using a reverse proxy, forward ordinary HTTP traffic and WebSocket upgrades to the configured BSM address. Provide HTTPS at the proxy when traffic crosses an untrusted network. Keep the backend's network exposure consistent with that deployment.

Configure `web.forwarded_allow_ips` for the actual trusted forwarding sources. Its default is `127.0.0.1`; trusting unrelated sources can let clients forge forwarding information. Check authentication and WebSocket behavior through the proxy before making the installation available to users.

## Appearance

See [theming](../web/theming.md) for supported frontend customization. Asset paths and frontend behavior follow the installed frontend package rather than a JavaScript build inside the backend checkout.

## Process ownership

Use one manager worker per configuration directory. Services and containers should signal graceful shutdown and allow its cleanup deadline. See [runtime control](web_runtime.md) for local stop commands, administrator shutdown, control credentials and restart policies.
