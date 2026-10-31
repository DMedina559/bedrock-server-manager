"""An explicit bearer-only Swagger session, isolated from browser cookies."""

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse


def configure_swagger(app: FastAPI) -> None:
    assets = Path(__file__).with_name("assets")
    presentation = (
        "<style>"
        + (assets / "swagger-access.css").read_text(encoding="utf-8")
        + "</style><script>"
        + (assets / "swagger-access.js").read_text(encoding="utf-8")
        + "</script>"
    )

    @app.get("/docs", include_in_schema=False)
    async def swagger(request: Request) -> HTMLResponse:
        prefix = request.scope.get("root_path", "").rstrip("/")
        response = get_swagger_ui_html(
            openapi_url=f"{prefix}{app.openapi_url}",
            title=f"{app.title} - Swagger UI",
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui.css",
            swagger_ui_parameters={
                **(app.swagger_ui_parameters or {}),
                "persistAuthorization": False,
                "withCredentials": False,
                "showExtensions": True,
            },
        )
        # FastAPI serializes parameters as JSON. Inject an actual JS function,
        # and wrap fetch before Swagger loads so token and operation requests
        # have the same verified browser transport policy.
        transport = """<script>
const swaggerFetch = window.fetch.bind(window);
window.fetch = (input, init = {}) => swaggerFetch(input, {...init, credentials: 'omit'});
</script>"""
        body = bytes(response.body).decode()
        body = body.replace(
            "<script src=", presentation + transport + "\n<script src=", 1
        )
        body = body.replace(
            "const ui = SwaggerUIBundle({",
            'const ui = SwaggerUIBundle({\nplugins: [SwaggerAccessPlugin],\nrequestInterceptor: request => { request.credentials = "omit";\nif (new URL(request.url).pathname.endsWith("/auth/token")) {\n  request.headers = {...request.headers, "X-BSM-Auth-Mode": "bearer"};\n  const code = ui.getSystem().fn.consumeAuthenticatorCode?.();\n  if (code) { const form = new URLSearchParams(request.body); form.set("otp", code); request.body = form.toString(); }\n}\nreturn request; },',
        )
        # Resolve relative OAuth token URLs against the trusted ingress prefix,
        # rather than /docs or a deep page URL.
        base = json.dumps(f"{prefix}/")
        body = body.replace(
            "requestInterceptor: request => {",
            f"requestInterceptor: request => {{ request.url = new URL(request.url, window.location.origin + {base}).href;",
        )
        return HTMLResponse(body, headers={"Cache-Control": "no-store"})
