"""Proxy ingress and HTTPS integration coverage using the real application."""

from html.parser import HTMLParser
from urllib.parse import urlsplit

import bsm_frontend
import pytest
from httpx2 import ASGITransport, AsyncClient

from bedrock_server_manager.web.app import create_web_app


class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.bases = []
        self.assets = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "base":
            self.bases.append(attributes)
        if tag in ("script", "link"):
            url = attributes.get("src") or attributes.get("href")
            if url and url.startswith("./"):
                self.assets.append(url)


@pytest.mark.parametrize(
    "prefix",
    ["", "/api/hassio_ingress/token", "/app", "/proxy/app/token", "/proxy/%C3%A9"],
)
async def test_frontend_assets_through_proxy(app_context, prefix):
    app = create_web_app(app_context)
    headers = {"X-Ingress-Path": prefix, "X-Forwarded-Proto": "https"}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://bsm.test"
    ) as client:
        response = await client.get("/app/settings/account", headers=headers)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        parser = AssetParser()
        parser.feed(response.text)
        assert len(parser.bases) == 1
        assert parser.bases[0]["href"] == prefix + "/app/"
        assert parser.bases[0]["data-api-base"] == prefix
        assert parser.assets
        for asset in parser.assets:
            # Emulate the gateway removing its external prefix.
            result = await client.get(
                "/app/" + asset.removeprefix("./"), headers=headers
            )
            assert result.status_code == 200, asset
            assert "text/html" not in result.headers.get("content-type", "")
        redirect = await client.get("/", headers=headers, follow_redirects=False)
        location = urlsplit(redirect.headers["location"])
        assert location.scheme == "https"
        assert location.path == prefix + "/app"


async def test_static_cache_policy(app_context, tmp_path, monkeypatch):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "index-Ab123456.js").write_text("export default 1;")
    (assets / "mutable.css").write_text("body {}")
    themes = tmp_path / "themes"
    themes.mkdir()
    (themes / "custom-Ab123456.css").write_text("body {}")
    await app_context.settings.set("paths.themes", str(themes))
    monkeypatch.setattr(bsm_frontend, "get_static_dir", lambda: str(tmp_path))
    async with AsyncClient(
        transport=ASGITransport(app=create_web_app(app_context)),
        base_url="http://bsm.test",
    ) as client:
        bundle = await client.get("/app/assets/index-Ab123456.js")
        assert bundle.status_code == 200
        assert bundle.headers["cache-control"] == "public, max-age=31536000, immutable"
        mutable = await client.get("/app/assets/mutable.css")
        assert mutable.headers["cache-control"] == "no-cache"
        theme = await client.get("/themes/custom-Ab123456.css")
        assert theme.headers["cache-control"] == "no-cache"
        cached = await client.get(
            "/app/assets/index-Ab123456.js",
            headers={"If-None-Match": bundle.headers["etag"]},
        )
        assert cached.status_code == 304
        assert cached.headers["cache-control"] == bundle.headers["cache-control"]


@pytest.mark.parametrize(
    "prefix",
    [
        "//evil.test",
        "https://evil.test",
        "/../escape",
        "/%2e%2e/escape",
        "/prefix?x=1",
        "/prefix%5cescape",
    ],
)
async def test_reject_invalid_trusted_ingress(app_context, prefix):
    async with AsyncClient(
        transport=ASGITransport(app=create_web_app(app_context)),
        base_url="http://bsm.test",
    ) as client:
        response = await client.get("/app/", headers={"X-Ingress-Path": prefix})
        assert response.status_code == 400


async def test_untrusted_headers_do_not_change_urls(app_context):
    transport = ASGITransport(
        app=create_web_app(app_context), client=("192.0.2.5", 1234)
    )
    async with AsyncClient(transport=transport, base_url="http://bsm.test") as client:
        response = await client.get(
            "/",
            headers={"X-Ingress-Path": "/evil", "X-Forwarded-Proto": "https"},
            follow_redirects=False,
        )
        assert response.headers["location"] == "http://bsm.test/app"


@pytest.mark.parametrize("trusted", [True, False])
async def test_setup_https_cookie_policy(app_context, trusted):
    peer = "127.0.0.1" if trusted else "192.0.2.5"
    transport = ASGITransport(app=create_web_app(app_context), client=(peer, 1234))
    async with AsyncClient(transport=transport, base_url="http://bsm.test") as client:
        response = await client.post(
            "/api/setup/create-first-user",
            json={"username": "admin", "password": "securepassword"},
            headers={
                "X-Ingress-Path": "/ingress/token",
                "X-Forwarded-Proto": "https",
                "X-Forwarded-For": "203.0.113.5",
            },
        )
        assert response.status_code == 200
        cookie = response.headers["set-cookie"]
        assert ("Secure" in cookie) == trusted
        assert "HttpOnly" in cookie
        assert "SameSite=lax" in cookie
        assert ("Path=/ingress/token" if trusted else "Path=/;") in cookie


async def test_login_refresh_logout_proxy_cookie_policy(app_context, test_user):
    transport = ASGITransport(app=create_web_app(app_context))
    headers = {"X-Ingress-Path": "/ingress/token", "X-Forwarded-Proto": "https"}
    async with AsyncClient(transport=transport, base_url="http://bsm.test") as client:
        login = await client.post(
            "/auth/token",
            data={"username": "testuser", "password": "testpassword"},
            headers=headers,
        )
        assert login.status_code == 200
        headers["Authorization"] = "Bearer " + login.json()["access_token"]
        refresh = await client.post("/auth/reauth", headers=headers)
        logout = await client.get("/auth/logout", headers=headers)
        for response in (login, refresh, logout):
            assert response.status_code == 200
            cookie = response.headers["set-cookie"]
            assert "Secure" in cookie and "Path=/ingress/token" in cookie
            assert response.headers["cache-control"] == "no-store"
        assert "Max-Age=0" in logout.headers["set-cookie"]


async def test_websocket_authentication_behind_ingress(
    websocket_client, app_context, test_user
):
    import json

    from bedrock_server_manager.utils.auth import create_access_token

    token = await create_access_token(app_context, {"sub": test_user.username})
    async with websocket_client(
        additional_headers={"X-Ingress-Path": "/app", "X-Forwarded-Proto": "https"}
    ) as socket:
        await socket.send(json.dumps({"action": "authenticate", "token": token}))
        result = json.loads(await socket.recv())
        assert result["status"] == "success"
        await socket.send(
            json.dumps({"action": "subscribe", "topic": "server_updates"})
        )
        assert json.loads(await socket.recv())["status"] == "success"


async def test_configured_proxy_network(app_context):
    await app_context.settings.set("web.forwarded_allow_ips", "192.0.2.0/24")
    transport = ASGITransport(
        app=create_web_app(app_context), client=("192.0.2.7", 1234)
    )
    async with AsyncClient(transport=transport, base_url="http://bsm.test") as client:
        response = await client.get(
            "/",
            headers={
                "X-Ingress-Path": "/prefix/",
                "X-Forwarded-Proto": "https",
                "X-Forwarded-For": "203.0.113.5",
            },
            follow_redirects=False,
        )
        assert response.headers["location"] == "https://bsm.test/prefix/app"


async def test_registration_links_use_external_https_prefix(
    app_context, test_admin_user
):
    from bedrock_server_manager.utils.auth import create_access_token

    token = await create_access_token(app_context, {"sub": test_admin_user.username})
    headers = {
        "X-Ingress-Path": "/ingress/token",
        "X-Forwarded-Proto": "https",
        "Authorization": "Bearer " + token,
    }
    async with AsyncClient(
        transport=ASGITransport(app=create_web_app(app_context)),
        base_url="http://bsm.test",
    ) as client:
        response = await client.post(
            "/api/register/generate-token", json={"role": "user"}, headers=headers
        )
        assert response.status_code == 200
        assert response.json()["registration_url"].startswith(
            "https://bsm.test/ingress/token/app/register/"
        )
