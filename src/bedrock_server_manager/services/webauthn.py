"""Standards-compliant WebAuthn (Passkey) registration and assertion verification."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import struct
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding, rsa

from ..web.origin import browser_origin

COSE_KTY_OKP = 1
COSE_KTY_EC2 = 2
COSE_KTY_RSA = 3

COSE_ALG_ES256 = -7
COSE_ALG_EDDSA = -8
COSE_ALG_RS256 = -257

COSE_CRV_P256 = 1
COSE_CRV_ED25519 = 6

SUPPORTED_PUBKEY_ALGS = (COSE_ALG_ES256, COSE_ALG_EDDSA, COSE_ALG_RS256)

FLAG_UP = 0x01
FLAG_UV = 0x04
FLAG_BE = 0x08
FLAG_BS = 0x10
FLAG_AT = 0x40


class WebAuthnError(ValueError):
    """Raised when WebAuthn ceremony data or cryptographic verification fails."""


class PasskeyCounterRegressionError(WebAuthnError):
    """Raised when an authenticator's signature counter does not advance."""


@dataclass(frozen=True)
class VerifiedPasskeyRegistration:
    credential_id: str
    public_key: str
    sign_count: int
    aaguid: str
    user_verified: bool
    backup_eligible: bool
    backup_state: bool


@dataclass(frozen=True)
class VerifiedPasskeyAssertion:
    credential_id: str
    sign_count: int
    user_verified: bool
    backup_eligible: bool
    backup_state: bool


def b64url_encode(data: bytes) -> str:
    """Encode bytes as unpadded base64url ASCII."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(value: str) -> bytes:
    """Strictly decode an unpadded or padded base64url string."""
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 22000
        or not value.isascii()
    ):
        raise WebAuthnError("Invalid base64url value")
    cleaned = value.rstrip("=")
    if any(
        ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        for ch in cleaned
    ):
        raise WebAuthnError("Invalid base64url characters")
    padded = cleaned + "=" * ((4 - len(cleaned) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (binascii.Error, ValueError) as error:
        raise WebAuthnError("Malformed base64url data") from error
    if b64url_encode(raw) != cleaned:
        raise WebAuthnError("Non-canonical base64url encoding")
    return raw


def _read_cbor_length(data: bytes, offset: int, info: int) -> tuple[int, int]:
    if info < 24:
        return info, offset
    if info == 24:
        if offset + 1 > len(data):
            raise WebAuthnError("Truncated CBOR uint8")
        return data[offset], offset + 1
    if info == 25:
        end = offset + 2
        if end > len(data):
            raise WebAuthnError("Truncated CBOR uint16")
        return struct.unpack(">H", data[offset:end])[0], end
    if info == 26:
        end = offset + 4
        if end > len(data):
            raise WebAuthnError("Truncated CBOR uint32")
        return struct.unpack(">I", data[offset:end])[0], end
    if info == 27:
        end = offset + 8
        if end > len(data):
            raise WebAuthnError("Truncated CBOR uint64")
        return struct.unpack(">Q", data[offset:end])[0], end
    raise WebAuthnError("Unsupported CBOR additional information")


def decode_cbor_item(data: bytes, offset: int = 0, depth: int = 0) -> tuple[Any, int]:
    """Decode one definite-length CBOR item and return ``(value, next_offset)``."""
    if depth > 16:
        raise WebAuthnError("CBOR nesting depth exceeded")
    if offset >= len(data):
        raise WebAuthnError("Unexpected end of CBOR input")
    initial = data[offset]
    offset += 1
    major = initial >> 5
    info = initial & 0x1F
    length, offset = _read_cbor_length(data, offset, info)

    if major == 0:
        return length, offset
    if major == 1:
        return -1 - length, offset
    if major == 2:
        end = offset + length
        if end > len(data):
            raise WebAuthnError("Truncated CBOR byte string")
        return data[offset:end], end
    if major == 3:
        end = offset + length
        if end > len(data):
            raise WebAuthnError("Truncated CBOR text string")
        try:
            return data[offset:end].decode("utf-8"), end
        except UnicodeDecodeError as error:
            raise WebAuthnError("Invalid UTF-8 in CBOR text string") from error
    if major == 4:
        if length > 256:
            raise WebAuthnError("CBOR array length exceeded")
        items = []
        for _ in range(length):
            item, offset = decode_cbor_item(data, offset, depth + 1)
            items.append(item)
        return items, offset
    if major == 5:
        if length > 256:
            raise WebAuthnError("CBOR map length exceeded")
        mapping: dict[Any, Any] = {}
        for _ in range(length):
            key, offset = decode_cbor_item(data, offset, depth + 1)
            if not isinstance(key, (int, str, bytes)):
                raise WebAuthnError("Unsupported CBOR map key type")
            if key in mapping:
                raise WebAuthnError("Duplicate CBOR map key")
            val, offset = decode_cbor_item(data, offset, depth + 1)
            mapping[key] = val
        return mapping, offset
    if major == 7:
        if info == 20:
            return False, offset
        if info == 21:
            return True, offset
        if info == 22:
            return None, offset
    raise WebAuthnError("Unsupported CBOR major type")


def decode_cbor(data: bytes) -> Any:
    """Decode a complete CBOR buffer with no trailing bytes."""
    value, offset = decode_cbor_item(data, 0)
    if offset != len(data):
        raise WebAuthnError("Unexpected trailing bytes in CBOR payload")
    return value


def _load_cose_public_key(cose_bytes: bytes) -> tuple[int, Any]:
    cose_map = decode_cbor(cose_bytes)
    if not isinstance(cose_map, dict):
        raise WebAuthnError("COSE public key must be a CBOR map")
    kty = cose_map.get(1)
    alg = cose_map.get(3)
    if kty == COSE_KTY_EC2 and alg == COSE_ALG_ES256:
        crv = cose_map.get(-1)
        x = cose_map.get(-2)
        y = cose_map.get(-3)
        if (
            crv != COSE_CRV_P256
            or not isinstance(x, bytes)
            or not isinstance(y, bytes)
            or len(x) != 32
            or len(y) != 32
        ):
            raise WebAuthnError("Invalid ES256 COSE public key parameters")
        try:
            numbers = ec.EllipticCurvePublicNumbers(
                int.from_bytes(x, "big"),
                int.from_bytes(y, "big"),
                ec.SECP256R1(),
            )
            return alg, numbers.public_key()
        except ValueError as error:
            raise WebAuthnError("Invalid EC P-256 public key coordinates") from error

    if kty == COSE_KTY_OKP and alg == COSE_ALG_EDDSA:
        crv = cose_map.get(-1)
        x = cose_map.get(-2)
        if crv != COSE_CRV_ED25519 or not isinstance(x, bytes) or len(x) != 32:
            raise WebAuthnError("Invalid Ed25519 COSE public key parameters")
        try:
            return alg, ed25519.Ed25519PublicKey.from_public_bytes(x)
        except ValueError as error:
            raise WebAuthnError("Invalid Ed25519 public key") from error

    if kty == COSE_KTY_RSA and alg == COSE_ALG_RS256:
        n = cose_map.get(-1)
        e = cose_map.get(-2)
        if (
            not isinstance(n, bytes)
            or not isinstance(e, bytes)
            or not 256 <= len(n) <= 1024
            or not 1 <= len(e) <= 8
        ):
            raise WebAuthnError("Invalid RS256 COSE public key parameters")
        try:
            rsa_numbers = rsa.RSAPublicNumbers(
                int.from_bytes(e, "big"),
                int.from_bytes(n, "big"),
            )
            return alg, rsa_numbers.public_key()
        except ValueError as error:
            raise WebAuthnError("Invalid RSA public key") from error

    raise WebAuthnError("Unsupported COSE key type or algorithm")


def resolve_rp_and_origins(request: Any, settings: Any) -> tuple[str, set[str]]:
    """Determine the relying party ID and allowed WebAuthn origins for ``request``."""
    primary_origin = browser_origin(request)
    configured = settings.get("web.cors_origins", ()) or ()
    allowed: set[str] = {primary_origin}
    for item in configured:
        if isinstance(item, str) and item.strip():
            parsed = urlsplit(item.strip())
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                allowed.add(f"{parsed.scheme}://{parsed.netloc}")
    header_origin = request.headers.get("origin")
    selected_origin = (
        header_origin if header_origin and header_origin in allowed else primary_origin
    )
    hostname = urlsplit(selected_origin).hostname or "localhost"
    return hostname.lower(), allowed


def _verify_client_data(
    client_data_b64: str,
    *,
    expected_type: str,
    expected_challenge: str,
    expected_rp_id: str,
    allowed_origins: set[str],
) -> bytes:
    raw = b64url_decode(client_data_b64)
    if len(raw) > 8192:
        raise WebAuthnError("clientDataJSON exceeds maximum size")
    try:
        client_data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WebAuthnError("Malformed clientDataJSON") from error
    if not isinstance(client_data, dict):
        raise WebAuthnError("clientDataJSON must be a JSON object")
    if client_data.get("type") != expected_type:
        raise WebAuthnError("Unexpected WebAuthn ceremony type")
    challenge = client_data.get("challenge")
    if not isinstance(challenge, str) or not hmac.compare_digest(
        challenge, expected_challenge
    ):
        raise WebAuthnError("WebAuthn challenge mismatch")
    origin = client_data.get("origin")
    if not isinstance(origin, str) or origin not in allowed_origins:
        raise WebAuthnError("WebAuthn origin is not permitted")
    origin_host = (urlsplit(origin).hostname or "").lower()
    rp_id = expected_rp_id.lower()
    if origin_host != rp_id and not origin_host.endswith("." + rp_id):
        raise WebAuthnError("WebAuthn origin does not match relying party ID")
    if client_data.get("crossOrigin") is True:
        raise WebAuthnError("Cross-origin WebAuthn ceremonies are not permitted")
    return raw


def verify_registration_response(
    *,
    credential: dict[str, Any],
    expected_challenge: str,
    expected_rp_id: str,
    allowed_origins: set[str],
    require_user_verification: bool = False,
) -> VerifiedPasskeyRegistration:
    """Verify a ``navigator.credentials.create()`` public-key response."""
    response = credential.get("response")
    if not isinstance(response, dict):
        raise WebAuthnError("Missing registration response payload")
    client_data_b64 = response.get("clientDataJSON")
    attestation_b64 = response.get("attestationObject")
    if not isinstance(client_data_b64, str) or not isinstance(attestation_b64, str):
        raise WebAuthnError("Missing clientDataJSON or attestationObject")

    _verify_client_data(
        client_data_b64,
        expected_type="webauthn.create",
        expected_challenge=expected_challenge,
        expected_rp_id=expected_rp_id,
        allowed_origins=allowed_origins,
    )

    attestation_raw = b64url_decode(attestation_b64)
    if len(attestation_raw) > 16384:
        raise WebAuthnError("attestationObject exceeds maximum size")
    attestation = decode_cbor(attestation_raw)
    if not isinstance(attestation, dict):
        raise WebAuthnError("attestationObject must be a CBOR map")
    auth_data = attestation.get("authData")
    if not isinstance(auth_data, bytes) or len(auth_data) < 55:
        raise WebAuthnError("Invalid authenticator data in attestationObject")

    rp_id_hash = auth_data[:32]
    expected_hash = hashlib.sha256(expected_rp_id.lower().encode("utf-8")).digest()
    if not hmac.compare_digest(rp_id_hash, expected_hash):
        raise WebAuthnError("Relying party ID hash mismatch")

    flags = auth_data[32]
    if not (flags & FLAG_UP):
        raise WebAuthnError("Authenticator did not confirm user presence")
    user_verified = bool(flags & FLAG_UV)
    if require_user_verification and not user_verified:
        raise WebAuthnError("Authenticator did not verify user identity")
    if not (flags & FLAG_AT):
        raise WebAuthnError("Attested credential data missing from registration")
    backup_eligible = bool(flags & FLAG_BE)
    backup_state = bool(flags & FLAG_BS)
    if backup_state and not backup_eligible:
        raise WebAuthnError("Invalid authenticator backup state flags")

    sign_count = struct.unpack(">I", auth_data[33:37])[0]
    aaguid_bytes = auth_data[37:53]
    aaguid = str(uuid.UUID(bytes=aaguid_bytes))
    cred_len = struct.unpack(">H", auth_data[53:55])[0]
    cred_end = 55 + cred_len
    if cred_len < 1 or cred_len > 1023 or cred_end >= len(auth_data):
        raise WebAuthnError("Invalid attested credential ID length")
    cred_id_bytes = auth_data[55:cred_end]
    cred_id_b64 = b64url_encode(cred_id_bytes)

    outer_id = credential.get("rawId") or credential.get("id")
    if isinstance(outer_id, str) and outer_id != cred_id_b64:
        raise WebAuthnError("Credential ID does not match attested credential data")

    cose_item, next_offset = decode_cbor_item(auth_data, cred_end)
    if not isinstance(cose_item, dict):
        raise WebAuthnError("Invalid attested credential public key")
    cose_bytes = auth_data[cred_end:next_offset]
    _load_cose_public_key(cose_bytes)

    return VerifiedPasskeyRegistration(
        credential_id=cred_id_b64,
        public_key=b64url_encode(cose_bytes),
        sign_count=sign_count,
        aaguid=aaguid,
        user_verified=user_verified,
        backup_eligible=backup_eligible,
        backup_state=backup_state,
    )


def verify_authentication_response(
    *,
    credential: dict[str, Any],
    expected_challenge: str,
    expected_rp_id: str,
    allowed_origins: set[str],
    public_key_b64: str,
    stored_sign_count: int,
    require_user_verification: bool = False,
) -> VerifiedPasskeyAssertion:
    """Verify a ``navigator.credentials.get()`` assertion against a stored passkey."""
    response = credential.get("response")
    if not isinstance(response, dict):
        raise WebAuthnError("Missing authentication response payload")
    client_data_b64 = response.get("clientDataJSON")
    auth_data_b64 = response.get("authenticatorData")
    signature_b64 = response.get("signature")
    if (
        not isinstance(client_data_b64, str)
        or not isinstance(auth_data_b64, str)
        or not isinstance(signature_b64, str)
    ):
        raise WebAuthnError("Missing authenticator assertion fields")

    raw_id = credential.get("rawId") or credential.get("id")
    if not isinstance(raw_id, str):
        raise WebAuthnError("Missing credential identifier")
    credential_id = b64url_encode(b64url_decode(raw_id))

    client_data_raw = _verify_client_data(
        client_data_b64,
        expected_type="webauthn.get",
        expected_challenge=expected_challenge,
        expected_rp_id=expected_rp_id,
        allowed_origins=allowed_origins,
    )
    auth_data = b64url_decode(auth_data_b64)
    if not 37 <= len(auth_data) <= 16384:
        raise WebAuthnError("authenticatorData is too short")

    rp_id_hash = auth_data[:32]
    expected_hash = hashlib.sha256(expected_rp_id.lower().encode("utf-8")).digest()
    if not hmac.compare_digest(rp_id_hash, expected_hash):
        raise WebAuthnError("Relying party ID hash mismatch")

    flags = auth_data[32]
    if not (flags & FLAG_UP):
        raise WebAuthnError("Authenticator did not confirm user presence")
    user_verified = bool(flags & FLAG_UV)
    if require_user_verification and not user_verified:
        raise WebAuthnError("Authenticator did not verify user identity")
    backup_eligible = bool(flags & FLAG_BE)
    backup_state = bool(flags & FLAG_BS)
    if backup_state and not backup_eligible:
        raise WebAuthnError("Invalid authenticator backup state flags")

    sign_count = struct.unpack(">I", auth_data[33:37])[0]
    signature = b64url_decode(signature_b64)
    if len(signature) > 1024:
        raise WebAuthnError("Passkey signature exceeds maximum size")
    signed_data = auth_data + hashlib.sha256(client_data_raw).digest()

    alg, public_key = _load_cose_public_key(b64url_decode(public_key_b64))
    try:
        if alg == COSE_ALG_ES256:
            public_key.verify(signature, signed_data, ec.ECDSA(hashes.SHA256()))
        elif alg == COSE_ALG_EDDSA:
            public_key.verify(signature, signed_data)
        elif alg == COSE_ALG_RS256:
            public_key.verify(
                signature, signed_data, padding.PKCS1v15(), hashes.SHA256()
            )
        else:
            raise WebAuthnError("Unsupported passkey signature algorithm")
    except InvalidSignature as error:
        raise WebAuthnError("Invalid passkey assertion signature") from error

    if stored_sign_count > 0 or sign_count > 0:
        if sign_count <= stored_sign_count:
            raise PasskeyCounterRegressionError(
                "Passkey signature counter did not advance"
            )

    return VerifiedPasskeyAssertion(
        credential_id=credential_id,
        sign_count=sign_count,
        user_verified=user_verified,
        backup_eligible=backup_eligible,
        backup_state=backup_state,
    )
