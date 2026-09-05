from fastapi.staticfiles import StaticFiles


class IngressAwareStaticFiles(StaticFiles):
    """
    Custom StaticFiles class to handle Ingress stripped paths.
    Temporarily strips the ingress path from `scope['root_path']` during `__call__`
    to prevent `starlette.routing.get_route_path` from failing to match.
    """

    async def __call__(self, scope, receive, send):
        original_root_path = scope.get("root_path", "")

        ingress_path = ""
        headers = dict(scope.get("headers", []))
        if b"x-ingress-path" in headers:
            ingress_path = headers[b"x-ingress-path"].decode("latin-1")

            if original_root_path.startswith(ingress_path):
                scope["root_path"] = original_root_path[
                    len(ingress_path) :  # noqa: E203
                ]

        try:
            await super().__call__(scope, receive, send)
        finally:
            scope["root_path"] = original_root_path
