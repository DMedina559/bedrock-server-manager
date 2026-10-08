def test_generated_plugin_api_matches_registry():
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    subprocess.run(
        [sys.executable, str(root / "scripts/generate_plugin_api.py"), "--check"],
        cwd=root,
        check=True,
        capture_output=True,
    )
