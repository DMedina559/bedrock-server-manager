# Hosting and web customization

Bind the web host to an address appropriate for its exposure. The default loopback binding is accessible from the local machine; a broader binding can expose BSM to other hosts.

## Reverse proxies

When using a reverse proxy, forward ordinary HTTP traffic and WebSocket upgrades to the configured BSM address. Provide HTTPS at the proxy when traffic crosses an untrusted network. Keep the backend's network exposure consistent with that deployment.

Configure `web.forwarded_allow_ips` for the actual trusted forwarding sources. Its default is `127.0.0.1`; trusting unrelated sources can let clients forge forwarding information. Check authentication and WebSocket behavior through the proxy before making the installation available to users.

### HTTPS and ingress paths

Terminate TLS at the reverse proxy and forward HTTP to BSM on a private,
restricted connection. Set `web.forwarded_allow_ips` to the immediate proxy's
IP address or CIDR, for example `192.168.1.1` for an OPNsense router or
`127.0.0.1` for a local add-on Nginx proxy. Avoid `*` unless the backend is
accessible only to trusted proxies. BSM checks the immediate peer before
processing `X-Forwarded-For`, `X-Forwarded-Proto`, or `X-Ingress-Path` for HTTP
and WebSocket requests. Uvicorn's outer proxy-header processing is disabled;
the application owns this policy so the original peer remains available.

For Home Assistant ingress or a subpath deployment, the gateway must **strip
the external prefix** before forwarding and set `X-Ingress-Path` to that
prefix. For example, the external URL `/api/hassio_ingress/token/app/` is
forwarded as `/app/`, with `X-Ingress-Path: /api/hassio_ingress/token`.
Preserving the prefix in the forwarded request is not supported. A trailing
slash on the header is normalized; malformed prefixes are rejected. Untrusted
clients' forwarding headers are ignored.

The frontend receives its prefix through the single `app-asset-base` element
in the served HTML. API, WebSocket, router, and asset URLs use that runtime
prefix. Deploy the updated frontend package alongside the backend. Session
cookies use the trusted HTTPS scheme and are scoped to the external prefix;
setup, login, refresh, and logout apply the same policy. Sign in again after
changing a deployment's prefix or upgrading from root-scoped cookies.

Configure HTTP-to-HTTPS redirects and HSTS at the TLS-terminating proxy.
BSM retains direct HTTP support for local deployments. An HTTPS frontend
requires an HTTPS remote backend, including its WebSocket connection.

A Caddy test site can simulate the gateway without Home Assistant:

```caddyfile
http://:8088 {
    redir /api/hassio_ingress/test-token /api/hassio_ingress/test-token/ 302
    handle_path /api/hassio_ingress/test-token/* {
        reverse_proxy 192.168.1.100:11325 {
            header_up X-Ingress-Path /api/hassio_ingress/test-token
        }
    }
    handle {
        respond "Outside ingress prefix" 404
    }
}
```

Replace the upstream IP, trust the router's upstream source IP in BSM, and
open `http://ROUTER_IP:8088/api/hassio_ingress/test-token/`. To test HTTPS, use
a TLS-enabled domain in Caddy instead. In the OPNsense plugin GUI, configure
a `handle_path` handler for `/api/hassio_ingress/test-token/*` and attach a
`header_up X-Ingress-Path /api/hassio_ingress/test-token` header. Test nested
page refreshes, redirects, downloads, themes, plugin content, and live updates.

HTML and token responses use `Cache-Control: no-store`. Fingerprinted build
bundles are immutable; mutable static files and custom themes revalidate.

## Appearance

See [theming](../web/theming.md) for supported frontend customization. Asset paths and frontend behavior follow the installed frontend package rather than a JavaScript build inside the backend checkout.

## Process ownership

Use one manager worker per configuration directory. Services and containers should signal graceful shutdown and allow its cleanup deadline. See [runtime control](web_runtime.md) for local stop commands, administrator shutdown, control credentials and restart policies.
