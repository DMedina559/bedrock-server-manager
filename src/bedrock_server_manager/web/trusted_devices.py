"""Select explicit remembered-device proofs without mixing bearer/cookie identities."""

from .cookies import cookie_options

HEADER = "x-bsm-trusted-device-token"


def cookie_name(owner_id):
    return "bsm_trusted_device_" + owner_id


def device_token(request, owner_id, supplied=None, *, cookie_login=None):
    if supplied is not None:
        return (
            supplied.get_secret_value()
            if hasattr(supplied, "get_secret_value")
            else supplied
        )
    if HEADER in request.headers:
        return request.headers[HEADER]
    if (
        cookie_login
        if cookie_login is not None
        else getattr(request.state, "credential_source", None) == "cookie"
    ):
        return request.cookies.get(cookie_name(owner_id))
    return None


def deliver_device(response, request, owner_id, issued, *, cookie_mode):
    if issued is None:
        return {}
    token, expiry = issued
    if cookie_mode:
        import time

        response.set_cookie(
            cookie_name(owner_id),
            token,
            max_age=max(0, expiry - int(time.time())),
            **cookie_options(request),
        )
    response.headers["Cache-Control"] = "no-store"
    return {
        "trusted_device_token": None if cookie_mode else token,
        "trusted_device_expires_at": expiry,
    }


def clear_device(response, request, owner_id):
    response.delete_cookie(cookie_name(owner_id), **cookie_options(request))
    response.headers["Cache-Control"] = "no-store"
