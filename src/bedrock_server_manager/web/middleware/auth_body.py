"""Bound authentication payloads before JSON/form parsing or cryptographic work."""

from starlette.responses import JSONResponse

from .ingress import route_path

AUTH_BODY_LIMIT = 65536


class AuthBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = route_path(scope) if scope["type"] == "http" else ""
        if (
            scope["type"] != "http"
            or scope.get("method") not in {"POST", "PUT", "PATCH"}
            or not (
                path.startswith("/auth/") or path.startswith("/api/account/security/")
            )
        ):
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = 0
        chunks = []
        received = 0
        if declared <= AUTH_BODY_LIMIT:
            while True:
                message = await receive()
                if message["type"] != "http.request":
                    chunks.append(message)
                    break
                received += len(message.get("body", b""))
                if received > AUTH_BODY_LIMIT:
                    break
                chunks.append(message)
                if not message.get("more_body", False):
                    break
        if declared > AUTH_BODY_LIMIT or received > AUTH_BODY_LIMIT:
            return await JSONResponse(
                {"detail": "Authentication request is too large."},
                status_code=413,
                headers={"Cache-Control": "no-store"},
            )(scope, receive, send)
        index = 0

        async def replay():
            nonlocal index
            if index < len(chunks):
                message = chunks[index]
                index += 1
                return message
            return await receive()

        return await self.app(scope, replay, send)
