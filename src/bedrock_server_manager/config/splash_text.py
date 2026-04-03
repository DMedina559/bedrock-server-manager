# bedrock_server_manager/config/splash_text.py
"""
Defines collections of splash text messages for the application.

These messages are typically displayed in the UI to add a bit of flavor
and humor, often related to Minecraft, server management, or the application itself.
The texts are categorized for potential varied use.
"""

# --- User Interface (UI) Related ---
SPLASH_TEXTS_UI = [
    "Based on Ore UI!",
    "Web UI!",
    "CLI",
    "CSS Themes!",
    "Command Line Power, Web UI Ease!",
    "CLI or GUI!",
    "CLI Power, Backup, Automate!",
    "GUI Power, Backup, Automate!",
    "Full Control: CLI & Web UI!",
    "Web & CLI Synergy!",
    "React + Vite Powered!",
    "Modern Web UI!",
    "New UI, Who Dis?",
    "NPM Installable UI!",
    "Remote UI Capabilities!",
    "Plugin Pages!",
    "?hidden=true",
]

# --- Core Features  ---
SPLASH_TEXTS_FEATURES = [
    "Check the Logs!",
    "Worlds, Addons, Backups - Oh My!",
    "Never Lose a World Again!",
    "Remember to bakcup!",
    "Auto Updates!",
    "Automated Awesomeness!",
    "Install, Configure, Automate!",
    "Update. Backup. Conquer.",
    "From World Installs to Web UI Control!",
    "Extend with Plugins!",
    "Customize with Themes!",
    "Native JSON UI for Plugins!",
]

# --- General Management & Control ---
SPLASH_TEXTS_MANAGEMENT = [
    "It Manages!",
    "Restart Required?",
    "Total Bedrock Control!",
    "Master Your Multiverse!",
    "Your Server Command Center!",
    "Rule Your Realm!",
    "The Ultimate Server Toolkit!",
    "Full Server Control!",
    "Manage Everything!",
    "Bedrock Solid Management!",
    "All Your Servers.",
    "Crafting Server Perfection!",
    "Your Server, Your World.",
    "Command the Blocks!",
]

# --- Ease of Use & Benefits ---
SPLASH_TEXTS_EASE_BENEFITS = [
    "Server Management Made Easy!",
    "Worry-Free Server Hosting!",
    "Keep Calm and Manage On!",
    "Spend More Time Playing!",
    "Like Creative Mode for Servers!",
    "Surviving Server Management!",
    "Simplify Your Server Life!",
    "Efficient Server Management!",
    "The Smart Server Solution!",
    "Simply Managed.",
    "More Managing, Less Mining",
]

# --- Power & Effectiveness ---
SPLASH_TEXTS_POWER = [
    "Automate. Administrate. Dominate!",
    "Robust. Reliable. Ready.",
    "Server Power Up!",
    "Bedrock Boss!",
]

# --- Minecraft & Bedrock Specific ---
SPLASH_TEXTS_MINECRAFT = [
    "Bedrockin'!",
    "Powered by Code (and maybe Coal)!",
    "No Hoglin here",
    "Minin' Blocks, Managin' Servers.",
    "Effortlessly Bedrock!",
]

# --- Open Source ---
SPLASH_TEXTS_OPENSOURCE = [
    "Open Source Power!",
    "MIT Licenced.",
    "Star the Github Project!",
    "Fork it, Fix it, Contribute it!",
    "Join the Open Source Revolution!",
    "Open Source, Open Possibilities!",
    "Open Source, Open Community!",
    "Open Source, Open Mind!",
    "Written in Python!",
    "Pythonic Power!",
    "Built with Python!",
]

# --- Miscellaneous ---
SPLASH_TEXTS_MISC = [
    "Astronomically Accurate!",
]

# --- Combined List ---
SPLASH_TEXTS: dict[str, list[str]] = {
    "UI": SPLASH_TEXTS_UI,
    "Features": SPLASH_TEXTS_FEATURES,
    "Management": SPLASH_TEXTS_MANAGEMENT,
    "Ease_Benefits": SPLASH_TEXTS_EASE_BENEFITS,
    "Power": SPLASH_TEXTS_POWER,
    "Minecraft": SPLASH_TEXTS_MINECRAFT,
    "OpenSource": SPLASH_TEXTS_OPENSOURCE,
    "Misc": SPLASH_TEXTS_MISC,
}
"""
A dictionary categorizing all splash text lists.
Keys are category names (e.g., "UI", "Features"), and values are the
corresponding lists of splash text strings.
"""
