# Install Bedrock Server Manager

BSM requires Python 3.11 or newer. Install it in a virtual environment so upgrades do not change other Python applications. The web frontend is installed as a separate Python dependency; building JavaScript is unnecessary for backend installation.

## Install a release

Create and activate an environment:

```sh
python -m venv .venv
```

On Linux, activate it with `source .venv/bin/activate`. In PowerShell, use `.venv\Scripts\Activate.ps1`. Then install:

```sh
python -m pip install --upgrade bedrock-server-manager
bedrock-server-manager --help
```

Use documentation matching your installed release. The development documentation may describe features unavailable in the latest stable package.

For a prerelease, run `python -m pip install --upgrade --pre bedrock-server-manager`. To select or return to a particular release, specify its exact version with `bedrock-server-manager==VERSION`; reinstalling without a version does not guarantee a downgrade.

## Run from source

```sh
 git clone https://github.com/DMedina559/bedrock-server-manager.git
 cd bedrock-server-manager
 git switch dev
 python -m pip install -e '.[dev,docs,cli]'
```

Activate your environment first. Development installations use the frontend package declared in `pyproject.toml`. Frontend development belongs in the separate `bsm-frontend` repository.

## Choose storage

The default database uses SQLite with the asynchronous `aiosqlite` driver. External databases are optional. Install the matching extra before configuring a database URL:

| Database | Extra | Explicit async URL prefix |
|---|---|---|
| PostgreSQL | `bedrock-server-manager[postgresql]` | `postgresql+asyncpg://` |
| MySQL | `bedrock-server-manager[mysql]` | `mysql+aiomysql://` |
| MariaDB | `bedrock-server-manager[mariadb]` | `mariadb+aiomysql://` |

Bootstrap options select configuration/data directories, logging and the database connection. Use `bedrock-server-manager --help` for available flags and [settings](../features/settings.md) for application settings. Back up existing storage before upgrading or changing database configuration.

Continue with [first startup](../general/quickstart.md) or [Docker](docker.md).
