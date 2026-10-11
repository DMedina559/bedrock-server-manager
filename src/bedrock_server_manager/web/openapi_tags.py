"""Ordered groups for the public core HTTP contract."""

OPENAPI_TAGS = [
    {"name": name, "description": description}
    for name, description in (
        ("Application", "Application information, health, and performance metrics."),
        ("Application Setup", "Initial application setup."),
        ("Application Settings", "Global configuration and lifecycle limits."),
        ("Authentication", "Sign in, reauthenticate, and sign out."),
        ("Registration", "Registration tokens and account creation."),
        ("Account Management", "Your profile, password, and appearance preferences."),
        ("User Management", "Administrative account and role management."),
        (
            "Server Management",
            "Discover, validate, install, update, and delete servers.",
        ),
        (
            "Server Processes",
            "Server status, resources, process control, and commands.",
        ),
        ("Server Settings", "Per-server application configuration."),
        ("Server Properties", "Bedrock server.properties configuration."),
        ("Server Access", "Server allowlists, player permissions, and bans."),
        ("Player Management", "Discover and manage the global player directory."),
        ("World Management", "Install, export, and reset server worlds."),
        ("Addon Management", "Install and configure server addons."),
        ("Backup & Restore", "Create, list, prune, and restore server backups."),
        ("Downloads", "Downloaded Bedrock versions and cleanup."),
        ("Plugin Management", "Plugin discovery, configuration, events, and reloads."),
        ("Background Tasks", "Managed operations and their outcomes."),
        ("Logs", "Application and server log history."),
        ("Audit Logs", "Administrative audit history."),
        ("Appearance", "Available themes and panorama backgrounds."),
    )
]
