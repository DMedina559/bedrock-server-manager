"""Resolve trusted proxy metadata before HTTP and WebSocket routing."""

from urllib.parse import quote, unquote

from starlette.responses import PlainTextResponse
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


def normalize_ingress_path(value: str) -> str:
    """Validate an external, encoded URL prefix with canonical URL escaping."""
    if value in ("", "/"):
        return ""
    decoded = unquote(value, errors="strict")
    if (
        not value.startswith("/")
        or value.startswith("//")
        or any(c in decoded for c in "\\?#")
        or any(ord(c) <= 32 or ord(c) == 127 for c in decoded)
        or any(part in (".", "..") for part in decoded.split("/"))
        or "//" in decoded
    ):
        raise ValueError("Invalid ingress path")
    return quote(decoded.rstrip("/"), safe="/-._~!$&'()*+,;=:@")


def route_path(scope):
    """Return the application path using a complete root-path boundary."""
    path = scope.get("path", "")
    root = scope.get("root_path", "").rstrip("/")
    if root and (path == root or path.startswith(root + "/")):
        return path[len(root) :] or "/"  # noqa: E203
    return path


class IngressMiddleware:
    """Accept proxy-stripped paths and metadata only from configured peers.

    Own forwarding here rather than in Uvicorn so trust is checked against the
    immediate peer before X-Forwarded-For replaces scope['client'].
    """

    def __init__(self, app, trusted_proxies="127.0.0.1"):
        self.app = app
        self.forwarded = ProxyHeadersMiddleware(
            self.dispatch, trusted_hosts=trusted_proxies
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        scope = dict(scope)
        peer = scope.get("client")
        scope["bsm.peer"] = peer
        # Reuse Uvicorn's exact host/network policy for every forwarding header.
        scope["bsm.trusted_proxy"] = (
            peer[0] if peer else None
        ) in self.forwarded.trusted_hosts
        await self.forwarded(scope, receive, send)

    async def dispatch(self, scope, receive, send):
        headers = dict(scope.get("headers", []))
        value = headers.get(b"x-ingress-path")
        if value is not None and scope["bsm.trusted_proxy"]:
            try:
                prefix = normalize_ingress_path(value.decode("ascii"))
            except (ValueError, UnicodeDecodeError):
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                else:
                    await PlainTextResponse("Invalid ingress path", status_code=400)(
                        scope, receive, send
                    )
                return
            scope["root_path"] = unquote(prefix)
            # ASGI paths are decoded; raw_path retains the external URL escapes.
            scope["path"] = unquote(prefix) + scope["path"]
            if "raw_path" in scope:
                scope["raw_path"] = prefix.encode("ascii") + scope["raw_path"]
        await self.app(scope, receive, send)
