# Installation

```{image} https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg
:alt: Bedrock Server Manager Icon
:width: 200px
:align: center
```

There are three ways to install Bedrock Server Manager, depending on your needs. For most users, the stable version is recommended.

---

## 1. Stable Version (Recommended)

This is the latest official, stable release. It has been tested and is suitable for most use cases. This command will install or upgrade to the latest stable version available on PyPI (Python Package Index).

```bash
pip install --upgrade bedrock-server-manager
```

**Installing a Specific Version**

If you need to install a specific version, you can do so by specifying the version with `==`.

```bash
# Example: Install exactly version 3.2.5
pip install bedrock-server-manager==3.2.5
```

You can find a list of all available versions in the [**Release History on PyPI**](https://pypi.org/project/bedrock-server-manager/#history).

---

## 2. Beta / Pre-Release Versions (For Testers)

Occasionally, pre-release versions will be published to PyPI for testing. These versions contain new features and are generally stable but may contain minor bugs.

To install the latest pre-release version, use the `--pre` flag with pip:

```bash
pip install --pre bedrock-server-manager
```

If you wish to return to the stable version later, you can run:
`pip install --force-reinstall bedrock-server-manager`

**Previewing the Next Release**

The `dev` branch is where all beta developments are merged before being bundled into a new stable release. To see the latest changes that are being prepared, you can browse the code and documentation on the [**`dev` branch**](https://github.com/DMedina559/bedrock-server-manager/tree/dev).

---

## 3. Development Versions (For Advanced Users & Contributors)

These versions are at the cutting edge and reflect the latest code, but they are not guaranteed to be stable. Use them if you want to test a specific new feature that isn't in a beta yet, or if you are contributing to the project.

**Install Directly from a GitHub Branch**

This is the way to test the code from a specific branch.

```bash
# Install the latest code from the 'main' branch
pip install git+https://github.com/DMedina559/bedrock-server-manager.git@main

# Or install from a specific feature branch
pip install git+https://github.com/DMedina559/bedrock-server-manager.git@name-of-the-branch
```

---

## 4. Environment Variables

You can configure the application using environment variables. These variables take precedence over the configuration file.

*   `BSM_DATA_DIR`: Overrides the default directory where the application stores data (servers, backups, etc.).
*   `BSM_DB_URL`: Overrides the database connection URL found in the configuration file.

## 5. Database Configuration

Bedrock Server Manager uses SQLAlchemy to connect to a database. By default, it uses a SQLite database, but you can configure it to use other databases like MySQL, MariaDB, or PostgreSQL.

To use a different database, you need to:
1.  Install the necessary database driver.
2.  Set the `db_url` in your configuration file OR set the `BSM_DB_URL` environment variable to the correct database connection string.

### Installing Database Drivers

You can install the required drivers as optional dependencies with `pip`.

*   **For MySQL:**
    ```bash
    pip install "bedrock-server-manager[mysql]"
    ```
    This will install both `mysqlclient` and `PyMySQL`.

*   **For MariaDB:**
    ```bash
    pip install "bedrock-server-manager[mariadb]"
    ```
    This will install both `mariadb` and `PyMySQL`.

*   **For PostgreSQL:**
    ```bash
    pip install "bedrock-server-manager[postgresql]"
    ```
    This will install `psycopg`.

### Database Connection URLs

Here are some examples of connection URLs for different databases.

*   **MySQL (using `mysqlclient`):**
    ```
    mysql://user:password@host/dbname
    ```

*   **MySQL (using `PyMySQL`):**
    ```
    mysql+pymysql://user:password@host/dbname
    ```

*   **MariaDB (using `mariadb`):**
    ```
    mariadb://user:password@host/dbname
    ```

*   **MariaDB (using `PyMySQL`):**
    ```
    mariadb+pymysql://user:password@host/dbname
    ```

*   **PostgreSQL (using `psycopg`):**
    ```
    postgresql+psycopg://user:password@host/dbname
    ```
