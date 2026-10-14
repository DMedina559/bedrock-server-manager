"""Generate or check deterministic Markdown references without starting BSM."""

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bedrock_server_manager.plugins.api_bridge import create_app_api  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location(
        "api_docs_generator", ROOT / "plugins/api_docs_generator.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Documentation formatter unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    generator = module.APIDocsGenerator.__new__(module.APIDocsGenerator)
    references = generator.format_reference_files(
        create_app_api("documentation", None).list_available_apis()
    )
    output = ROOT / "docs/source/plugins"
    if not args.check:
        generator.write_reference_files(output, references)
        return
    obsolete = [
        path
        for path in (output / "api").glob("*.md")
        if path.relative_to(output).as_posix() not in references
    ]
    if obsolete:
        parser.exit(1, "Obsolete plugin reference pages; regenerate documentation\n")

    for name, content in references.items():
        path = output / name
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                parser.exit(
                    1, f"{name} is stale; run python scripts/generate_plugin_docs.py\n"
                )
        else:
            path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
