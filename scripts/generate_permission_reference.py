"""Regenerate the built-in permission table without importing the HTTP application."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bedrock_server_manager.permissions import PERMISSION_SPECS  # noqa: E402

BEGIN = "<!-- BEGIN GENERATED PERMISSIONS -->"
END = "<!-- END GENERATED PERMISSIONS -->"
DEFAULT_PATH = ROOT / "docs/source/web/role_access_table.md"


def render_reference() -> str:
    categories = {str(key).split(":", 1)[0] for key in PERMISSION_SPECS}
    lines = [
        f"BSM defines {len(PERMISSION_SPECS)} built-in permissions across {len(categories)} categories, "
        "plus dynamic plugin permissions (`plugin:<plugin_name>:<perm>`). "
        "Default role grants remain an upper bound; credentials, server assignments and MFA policy can narrow effective access.",
        "",
        "| Permission | Category | `user` | `moderator` | `admin` | Server-scoped? | Delegatable to integration tokens? |",
        "|---|---|---|---|---|---|---|",
    ]
    for permission, spec in sorted(PERMISSION_SPECS.items()):
        roles = [
            "Yes" if role in spec.roles else "—"
            for role in ("user", "moderator", "admin")
        ]
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{permission}`",
                    str(permission).split(":", 1)[0],
                    *roles,
                    "Yes" if spec.resource == "server" else "No",
                    "Yes" if spec.delegatable else "**No**",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def updated_document(content: str) -> str:
    before, rest = content.split(BEGIN, 1)
    _, after = rest.split(END, 1)
    return before + BEGIN + "\n" + render_reference() + END + after


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    current = DEFAULT_PATH.read_text(encoding="utf-8")
    updated = updated_document(current)
    if args.check:
        if current != updated:
            raise SystemExit(
                "Permission reference is stale; run scripts/generate_permission_reference.py"
            )
    else:
        DEFAULT_PATH.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
