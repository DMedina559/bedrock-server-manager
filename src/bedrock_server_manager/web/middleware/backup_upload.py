"""Bound backup upload bodies before the multipart parser spools them to disk."""

from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse

from .ingress import route_path


class BackupUploadLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = route_path(scope) if scope["type"] == "http" else ""
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or not (
                path.startswith("/api/server/") and path.endswith("/backups/import")
            )
        ):
            return await self.app(scope, receive, send)
        context = scope["app"].state.app_context
        # Allow bounded multipart framing and a recovery-key form field.
        limit = context.settings.get("backups.max_archive_bytes", 1024**4) + 65536
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            length = 0
        if length > limit:
            return await JSONResponse(
                {"detail": "Backup exceeds upload limit."}, status_code=413
            )(scope, receive, send)
        received = 0
        exceeded = False

        async def bounded_receive():
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    # Starlette closes all partial spool files for multipart errors.
                    raise MultiPartException("Backup exceeds upload limit.")
            return message

        async def bounded_send(message):
            if exceeded and message["type"] == "http.response.start":
                message = {**message, "status": 413}
            await send(message)

        await self.app(scope, bounded_receive, bounded_send)
