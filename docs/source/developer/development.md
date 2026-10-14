# Contributor setup and validation

Start a feature branch from `dev` in your fork. Use the same Python environment for BSM, tests and documentation.

```sh
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e '.[dev,docs,cli]'
pre-commit install
```

Use the backend's dependency constraints. Development packages can require beta consumer releases; verify the exact required version is published rather than weakening constraints to make installation succeed.

## Checks

```sh
pre-commit run --all-files
python scripts/generate_plugin_api.py --check
python scripts/generate_plugin_docs.py --check
python scripts/check_api_callers.py
pytest tests/events tests/diagnostics tests/web/test_runtime.py
python -m sphinx -W --keep-going -b html docs/source docs/_build/html
```

Run focused tests during development and the appropriate full checks before submitting. Use `pytest --durations=25` to identify setup costs. CI covers supported minimum and maximum Python versions on Linux and Windows.

The Sphinx build retains `sphinx_github_changelog`; its release lookup uses `SPHINX_GITHUB_CHANGELOG_TOKEN` or `GITHUB_TOKEN` when available. Keep credentials in environment configuration, never in documentation or generated output.

The docs generator runs without starting BSM. Its plugin also exports a `plugin-reference` directory beneath the configured backup directory, with an API index, domain pages, shared models and events. Generated pages should be regenerated rather than hand-edited. See [contract development](contracts.md).
