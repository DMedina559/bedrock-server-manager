"""Browser origins use the immediate proxy's established trust boundary."""

import re
from urllib.parse import urlsplit

_HOST = re.compile(r"^(?:[A-Za-z0-9.-]+|\[[0-9A-Fa-f:]+\])(?::[0-9]{1,5})?$")


def browser_origin(connection):
    scheme = {"ws": "http", "wss": "https"}.get(
        connection.url.scheme, connection.url.scheme
    )
    host = connection.url.netloc
    forwarded = connection.headers.get("x-forwarded-host")
    if (
        connection.scope.get("bsm.trusted_proxy")
        and forwarded
        and _HOST.fullmatch(forwarded)
    ):
        try:
            candidate = urlsplit("//" + forwarded)
            if candidate.port is None or 0 < candidate.port <= 65535:
                host = forwarded
        except ValueError:
            pass
    return f"{scheme}://{host}"
