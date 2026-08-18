class IngressMiddleware:
    """
    ASGI Middleware that reads the 'X-Ingress-Path' header and sets the ASGI
    'root_path' accordingly. This is particularly important for WebSockets and
    routing when behind Home Assistant Ingress or other reverse proxies that
    mount the app at a dynamic path without stripping it.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            headers = dict(scope.get("headers", []))
            # ASGI headers are byte strings
            ingress_path = headers.get(b"x-ingress-path")

            if ingress_path:
                decoded_path = ingress_path.decode("latin-1")
                scope["root_path"] = decoded_path

                if not scope["path"].startswith(decoded_path):
                    # Combine without duplicating slashes
                    scope["path"] = (
                        decoded_path.rstrip("/") + "/" + scope["path"].lstrip("/")
                    )

        await self.app(scope, receive, send)
