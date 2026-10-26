# Documentation

Published documentation: https://bedrock-server-manager.readthedocs.io/en/latest/

For server recovery, see [Back up and restore a server](source/features/backups.md),
including portable archives, encryption keys, selective restore, schedules,
retention, external copies, and offline recovery.

Sources live in `docs/source`; contributor setup and validation are in
[the development guide](source/developer/development.md).
Generated plugin references come from `python scripts/generate_plugin_docs.py`.
Build with `python -m sphinx -W --keep-going -b html docs/source docs/_build/html`.
