"""Compare validated JSON snapshots without Python's bool/int equality alias."""

import json


def json_equal(left: object, right: object) -> bool:
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )
