"""Refresh the offline list from a reviewed SecLists commit, or verify bundled bytes.

Run --check without network access. Updates require an explicit immutable revision;
review the diff and upstream license before committing. Passwords never leave BSM.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.request import urlopen

DIRECTORY = Path(__file__).resolve().parents[1] / "src/bedrock_server_manager/data"
SOURCE = "Passwords/Common-Credentials/10k-most-common.txt"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", help="Reviewed 40-character upstream commit SHA")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        metadata = json.loads((DIRECTORY / "common-passwords-source.json").read_text())
        data = (DIRECTORY / "common-passwords.txt").read_bytes()
        assert hashlib.sha256(data).hexdigest() == metadata["sha256"]
        assert len(data.splitlines()) == metadata["entries"] >= 1000
        assert "MIT License" in (DIRECTORY / "common-passwords.LICENSE").read_text()
        print("Offline password blocklist provenance verified.")
        return
    if not args.revision or not re.fullmatch(r"[a-f0-9]{40}", args.revision):
        parser.error("Use --check or supply a reviewed immutable --revision.")
    base = f"https://raw.githubusercontent.com/danielmiessler/SecLists/{args.revision}/"
    downloads = {}
    for local, remote in (
        ("common-passwords.txt", SOURCE),
        ("common-passwords.LICENSE", "LICENSE"),
    ):
        with urlopen(base + remote, timeout=30) as response:
            value = response.read(2_000_001)
        if len(value) > 2_000_000:
            raise ValueError("Unexpected upstream data size")
        value.decode("utf-8")
        downloads[local] = value
    data = downloads["common-passwords.txt"]
    if (
        len(data.splitlines()) < 1000
        or "MIT License" not in downloads["common-passwords.LICENSE"].decode()
    ):
        raise ValueError("Review changed upstream data/license before updating")
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    for name, value in downloads.items():
        (DIRECTORY / name).write_bytes(value)
    (DIRECTORY / "common-passwords-source.json").write_text(
        json.dumps(
            {
                "repository": "https://github.com/danielmiessler/SecLists",
                "commit": args.revision,
                "path": SOURCE,
                "sha256": hashlib.sha256(data).hexdigest(),
                "license": "MIT",
                "entries": len(data.splitlines()),
            },
            indent=2,
        )
        + "\n"
    )
    print(
        "Updated offline password blocklist; review and commit the data and license together."
    )


if __name__ == "__main__":
    main()
