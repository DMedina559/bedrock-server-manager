"""End-to-end tests for passkeys (WebAuthn), unified .key credential stores, and step-up hardening."""

from __future__ import annotations

import hashlib
import json
import struct
import time
import uuid
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from sqlalchemy import update

from bedrock_server_manager.backups.credentials import (
    BACKUP_KEYRING_HEADER,
    BackupCredentials,
)
from bedrock_server_manager.db.models import LoginSession
from bedrock_server_manager.services.webauthn import (
    FLAG_AT,
    FLAG_BE,
    FLAG_BS,
    FLAG_UP,
    FLAG_UV,
    b64url_encode,
)
from bedrock_server_manager.web.auth import get_jwt_secret_key


def _cbor_uint(major: int, value: int) -> bytes:
    prefix = major << 5
    if value < 24:
        return bytes([prefix | value])
    if value < 256:
        return bytes([prefix | 24, value])
    if value < 65536:
        return bytes([prefix | 25]) + struct.pack(">H", value)
    return bytes([prefix | 26]) + struct.pack(">I", value)


def _cbor_encode(value) -> bytes:
    if isinstance(value, int):
        if value >= 0:
            return _cbor_uint(0, value)
        return _cbor_uint(1, -1 - value)
    if isinstance(value, bytes):
        return _cbor_uint(2, len(value)) + value
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return _cbor_uint(3, len(raw)) + raw
    if isinstance(value, list):
        return _cbor_uint(4, len(value)) + b"".join(
            _cbor_encode(item) for item in value
        )
    if isinstance(value, dict):
        parts = [_cbor_uint(5, len(value))]
        for k, v in value.items():
            parts.append(_cbor_encode(k))
            parts.append(_cbor_encode(v))
        return b"".join(parts)
    raise TypeError(f"Unsupported CBOR test type: {type(value)}")


class FakeAuthenticator:
    """Simulated FIDO2/WebAuthn authenticator supporting ES256 and EdDSA."""

    def __init__(self, *, alg: str = "ES256", sign_count: int = 1):
        self.alg = alg
        self.sign_count = sign_count
        self.credential_id_bytes = uuid.uuid4().bytes + uuid.uuid4().bytes
        self.credential_id = b64url_encode(self.credential_id_bytes)
        self.aaguid = uuid.UUID("00000000-0000-0000-0000-000000000001").bytes
        if alg == "ES256":
            self.private_key = ec.generate_private_key(ec.SECP256R1())
            numbers = self.private_key.public_key().public_numbers()
            x = numbers.x.to_bytes(32, "big")
            y = numbers.y.to_bytes(32, "big")
            self.cose_key = _cbor_encode({1: 2, 3: -7, -1: 1, -2: x, -3: y})
        elif alg == "EdDSA":
            self.private_key = ed25519.Ed25519PrivateKey.generate()
            x = self.private_key.public_key().public_bytes_raw()
            self.cose_key = _cbor_encode({1: 1, 3: -8, -1: 6, -2: x})
        else:
            raise ValueError(f"Unsupported algorithm: {alg}")

    def create(
        self,
        *,
        challenge: str,
        rp_id: str = "testserver",
        origin: str = "http://testserver",
        uv: bool = True,
        transports: list[str] | None = None,
    ) -> dict:
        client_data = json.dumps(
            {
                "type": "webauthn.create",
                "challenge": challenge,
                "origin": origin,
                "crossOrigin": False,
            }
        ).encode("utf-8")
        rp_id_hash = hashlib.sha256(rp_id.encode("utf-8")).digest()
        flags = FLAG_UP | FLAG_AT | FLAG_BE | FLAG_BS | (FLAG_UV if uv else 0)
        auth_data = (
            rp_id_hash
            + bytes([flags])
            + struct.pack(">I", self.sign_count)
            + self.aaguid
            + struct.pack(">H", len(self.credential_id_bytes))
            + self.credential_id_bytes
            + self.cose_key
        )
        attestation = _cbor_encode(
            {"fmt": "none", "attStmt": {}, "authData": auth_data}
        )
        return {
            "id": self.credential_id,
            "rawId": self.credential_id,
            "type": "public-key",
            "response": {
                "clientDataJSON": b64url_encode(client_data),
                "attestationObject": b64url_encode(attestation),
                "transports": transports or ["internal", "hybrid"],
            },
        }

    def get(
        self,
        *,
        challenge: str,
        rp_id: str = "testserver",
        origin: str = "http://testserver",
        uv: bool = True,
        increment: int = 1,
    ) -> dict:
        self.sign_count += increment
        client_data = json.dumps(
            {
                "type": "webauthn.get",
                "challenge": challenge,
                "origin": origin,
                "crossOrigin": False,
            }
        ).encode("utf-8")
        rp_id_hash = hashlib.sha256(rp_id.encode("utf-8")).digest()
        flags = FLAG_UP | FLAG_BE | FLAG_BS | (FLAG_UV if uv else 0)
        auth_data = rp_id_hash + bytes([flags]) + struct.pack(">I", self.sign_count)
        signed_payload = auth_data + hashlib.sha256(client_data).digest()
        if self.alg == "ES256":
            signature = self.private_key.sign(signed_payload, ec.ECDSA(hashes.SHA256()))
        else:
            signature = self.private_key.sign(signed_payload)
        return {
            "id": self.credential_id,
            "rawId": self.credential_id,
            "type": "public-key",
            "response": {
                "clientDataJSON": b64url_encode(client_data),
                "authenticatorData": b64url_encode(auth_data),
                "signature": b64url_encode(signature),
            },
        }


async def test_unified_key_stores_and_db_jwt_migration(tmp_path, app_context):
    """All secret stores live in credentials/*.key and migrate 4.0.2 DB jwt_secret_key."""
    from bedrock_server_manager.state.changeset import ChangeSet

    config_dir = Path(app_context.config_dir)
    credentials_dir = config_dir / "credentials"
    credentials_dir.mkdir(parents=True, exist_ok=True)

    # 1. Backup keyring stored in credentials/backup.key (# BSM-KEYRING-V1)
    backup_creds = BackupCredentials(str(config_dir))
    rotated = backup_creds.rotate()
    assert (
        backup_creds.get().secret.get_secret_value()
        == rotated.secret.get_secret_value()
    )
    assert (credentials_dir / "backup.key").is_file()
    assert (
        (credentials_dir / "backup.key")
        .read_text(encoding="utf-8")
        .startswith(BACKUP_KEYRING_HEADER)
    )

    # 2. 4.0.2 DB settings table web.jwt_secret_key -> credentials/jwt.key
    jwt_path = credentials_dir / "jwt.key"
    jwt_path.unlink(missing_ok=True)
    app_context.settings._jwt_signing_credential = None
    changes = ChangeSet()
    changes.add_setting("web")
    await app_context.storage.commit_settings(
        app_context.state,
        changes,
        lambda candidate: (
            candidate.set("web.jwt_secret_key", "migrated-402-db-jwt-secret"),
            candidate.set("web.jwt_key_initialized", False),
        ),
    )
    assert (
        await get_jwt_secret_key(app_context.settings) == "migrated-402-db-jwt-secret"
    )
    assert jwt_path.is_file()
    assert jwt_path.read_text(encoding="utf-8").strip() == "migrated-402-db-jwt-secret"
    assert app_context.settings.get("web.jwt_secret_key") is None
    assert app_context.settings.get("web.jwt_key_initialized") is True

    # 3. MFA encryption key stored in credentials/mfa.key
    mfa_path = credentials_dir / "mfa.key"
    mfa_path.unlink(missing_ok=True)
    cipher = app_context.session_service._cipher(create=True)
    token = cipher.encrypt(b"totp-secret")
    assert mfa_path.is_file()
    raw_fernet_key = mfa_path.read_bytes().strip()
    assert Fernet(raw_fernet_key).decrypt(token) == b"totp-secret"
    assert not (config_dir / "security").exists()


@pytest.mark.parametrize("alg", ["ES256", "EdDSA"])
async def test_passkey_registration_login_and_step_up_verification(
    auth_client, unauth_client, app_context, test_user, alg
):
    authenticator = FakeAuthenticator(alg=alg)

    # 1. Begin & complete registration
    begin = await auth_client.post("/api/account/security/passkeys/register/options")
    assert begin.status_code == 200, begin.text
    options = begin.json()
    challenge = options["public_key"]["challenge"]
    assert options["public_key"]["rp"]["id"] == "testserver"

    created = await auth_client.post(
        "/api/account/security/passkeys/register/verify",
        json={
            "challenge_id": options["challenge_id"],
            "name": f"YubiKey ({alg})",
            "credential": authenticator.create(challenge=challenge),
        },
    )
    assert created.status_code == 201, created.text
    passkey_info = created.json()
    passkey_id = passkey_info["id"]
    assert passkey_info["name"] == f"YubiKey ({alg})"
    assert passkey_info["active"] is True
    assert "public_key" not in passkey_info

    # Duplicate registration of same credential ID is rejected
    dup_begin = await auth_client.post(
        "/api/account/security/passkeys/register/options"
    )
    assert authenticator.credential_id in [
        item["id"] for item in dup_begin.json()["public_key"]["excludeCredentials"]
    ]

    # 2. Security status & list passkeys reflect enrolled passkey
    sec_status = (await auth_client.get("/api/account/security")).json()
    assert sec_status["passkeys_enabled"] is True
    assert sec_status["passkey_count"] == 1

    listed = await auth_client.get("/api/account/security/passkeys")
    assert listed.status_code == 200
    assert len(listed.json()) == 1 and listed.json()[0]["id"] == passkey_id

    # 3. Rename passkey
    renamed = await auth_client.patch(
        f"/api/account/security/passkeys/{passkey_id}",
        json={"name": "Primary Passkey"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Primary Passkey"

    # 4. Passwordless login with passkey (Bearer mode & Cookie mode)
    login_opts = await unauth_client.post(
        "/auth/passkey/options", json={"username": test_user.username}
    )
    assert login_opts.status_code == 200, login_opts.text
    login_data = login_opts.json()
    assert login_data["public_key"]["allowCredentials"][0]["id"] == (
        authenticator.credential_id
    )

    login_res = await unauth_client.post(
        "/auth/passkey/verify",
        json={
            "challenge_id": login_data["challenge_id"],
            "credential": authenticator.get(
                challenge=login_data["public_key"]["challenge"]
            ),
            "remember_me": True,
        },
    )
    assert login_res.status_code == 200, login_res.text
    bearer_token = login_res.json()["access_token"]
    assert bearer_token
    me = await unauth_client.get(
        "/api/account", headers={"Authorization": f"Bearer {bearer_token}"}
    )
    assert me.status_code == 200 and me.json()["username"] == test_user.username

    # Discoverable (usernameless) login in Cookie mode
    disc_opts = await unauth_client.post("/auth/passkey/options", json={})
    assert disc_opts.status_code == 200
    assert disc_opts.json()["public_key"]["allowCredentials"] == []
    cookie_login = await unauth_client.post(
        "/auth/passkey/verify",
        headers={"X-BSM-Auth-Mode": "cookie", "Origin": "http://testserver"},
        json={
            "challenge_id": disc_opts.json()["challenge_id"],
            "credential": authenticator.get(
                challenge=disc_opts.json()["public_key"]["challenge"]
            ),
        },
    )
    assert cookie_login.status_code == 200
    assert cookie_login.json()["access_token"] == ""
    assert "access_token_cookie" in cookie_login.cookies

    # 5. Step-up verification using passkey after verified_at expires
    account_info = (await auth_client.get("/api/account")).json()
    async with app_context.storage.transaction() as session:
        await session.execute(
            update(LoginSession)
            .where(LoginSession.id == account_info["session_id"])
            .values(verified_at=0)
        )
    # Deleting passkey while unverified requires recent auth
    denied = await auth_client.delete(f"/api/account/security/passkeys/{passkey_id}")
    assert denied.status_code == 403
    assert denied.headers["X-BSM-Recent-Auth"] == "required"

    step_opts = await auth_client.post("/api/account/security/passkeys/verify/options")
    assert step_opts.status_code == 200
    step_verified = await auth_client.post(
        "/api/account/security/passkeys/verify",
        json={
            "challenge_id": step_opts.json()["challenge_id"],
            "credential": authenticator.get(
                challenge=step_opts.json()["public_key"]["challenge"]
            ),
        },
    )
    assert step_verified.status_code == 200
    assert step_verified.json()["verified_until"] > int(time.time())

    # 6. Counter regression (cloned authenticator) is rejected and logged
    bad_opts = await unauth_client.post("/auth/passkey/options", json={})
    cloned = await unauth_client.post(
        "/auth/passkey/verify",
        json={
            "challenge_id": bad_opts.json()["challenge_id"],
            "credential": authenticator.get(
                challenge=bad_opts.json()["public_key"]["challenge"],
                increment=0,
            ),
        },
    )
    assert cloned.status_code == 401
    assert "regression" in cloned.json()["error"]["message"].lower()

    # 7. Revoke passkey after step-up verification
    revoked = await auth_client.delete(f"/api/account/security/passkeys/{passkey_id}")
    assert revoked.status_code == 200


async def test_passkey_satisfies_require_admin_mfa_policy(
    admin_auth_client, app_context
):
    await app_context.settings.set("security.require_admin_mfa", True)
    # Without TOTP or passkey enrolled, admin routes outside security enrollment are blocked
    blocked = await admin_auth_client.get("/api/settings/get")
    assert blocked.status_code == 403
    assert blocked.headers.get("X-BSM-MFA-Enrollment") == "required"

    # Admin can enroll a passkey while mfa_enrollment_required is active
    authenticator = FakeAuthenticator()
    begin = await admin_auth_client.post(
        "/api/account/security/passkeys/register/options"
    )
    assert begin.status_code == 200, begin.text
    created = await admin_auth_client.post(
        "/api/account/security/passkeys/register/verify",
        json={
            "challenge_id": begin.json()["challenge_id"],
            "name": "Admin Hardware Key",
            "credential": authenticator.create(
                challenge=begin.json()["public_key"]["challenge"]
            ),
        },
    )
    assert created.status_code == 201, created.text
    passkey_id = created.json()["id"]

    # Admin now has full permissions!
    allowed = await admin_auth_client.get("/api/settings/get")
    assert allowed.status_code == 200

    # Admin cannot revoke their sole MFA factor while require_admin_mfa is True
    cannot_remove = await admin_auth_client.delete(
        f"/api/account/security/passkeys/{passkey_id}"
    )
    assert cannot_remove.status_code == 403


async def test_sensitive_mutations_require_recent_verification_and_disable_revokes_tokens(
    admin_auth_client, auth_client, app_context, test_user, real_bedrock_server
):
    # Issue an integration token for test_user, then disable and re-enable test_user
    issued = await auth_client.post(
        "/api/account/tokens",
        json={"name": "CI Token", "permissions": ["account:read"]},
    )
    assert issued.status_code == 201
    raw_token = issued.json()["token"]

    await app_context.user_service.update_account(
        action="disable", user_id=test_user.id
    )
    await app_context.user_service.update_account(action="enable", user_id=test_user.id)
    assert (await app_context.access_service.authenticate(raw_token)) is None

    # Expire recent verification on admin_auth_client session
    account = (await admin_auth_client.get("/api/account")).json()
    async with app_context.storage.transaction() as session:
        await session.execute(
            update(LoginSession)
            .where(LoginSession.id == account["session_id"])
            .values(verified_at=0)
        )

    for method, path, body in [
        ("POST", "/api/backups/keys", None),
        (
            "POST",
            f"/api/server/{real_bedrock_server.server_name}/backups/example.bsmbackup/export",
            {},
        ),
        ("DELETE", f"/api/server/{real_bedrock_server.server_name}/delete", None),
        ("POST", "/api/settings/set", {"key": "retention.downloads", "value": 5}),
    ]:
        response = await admin_auth_client.request(method, path, json=body)
        assert response.status_code == 403, (method, path, response.text)
        assert response.headers.get("X-BSM-Recent-Auth") == "required"
