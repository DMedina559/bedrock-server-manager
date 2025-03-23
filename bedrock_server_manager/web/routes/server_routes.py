# bedrock-server-manager/bedrock_server_manager/web/routes/server_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
import json
from bedrock_server_manager import handlers
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.core.server import server as server_base
import os
import platform

server_bp = Blueprint("server_routes", __name__)


@server_bp.route("/")
def index():
    base_dir = get_base_dir()
    # Use the handler to get server status.
    status_response = handlers.get_all_servers_status_handler(base_dir=base_dir)
    if status_response["status"] == "error":
        flash(f"Error getting server status: {status_response['message']}", "error")
        servers = []  # Provide an empty list so the template doesn't break
    else:
        servers = status_response["servers"]
    return render_template("index.html", servers=servers)


@server_bp.route("/server/<server_name>/start", methods=["GET", "POST"])
def start_server_route(server_name):
    base_dir = get_base_dir()
    response = handlers.start_server_handler(server_name, base_dir)
    if response["status"] == "success":
        flash(f"Server '{server_name}' started successfully.", "success")
    else:
        flash(f"Error starting server '{server_name}': {response['message']}", "error")
    return redirect(url_for("server_routes.index"))


@server_bp.route("/server/<server_name>/stop", methods=["GET", "POST"])
def stop_server_route(server_name):
    base_dir = get_base_dir()
    response = handlers.stop_server_handler(server_name, base_dir)
    if response["status"] == "success":
        flash(f"Server '{server_name}' stopped successfully.", "success")
    else:
        flash(f"Error stopping server '{server_name}': {response['message']}", "error")
    return redirect(url_for("server_routes.index"))


@server_bp.route("/server/<server_name>/restart", methods=["GET", "POST"])
def restart_server_route(server_name):
    base_dir = get_base_dir()
    response = handlers.restart_server_handler(server_name, base_dir)
    if response["status"] == "success":
        flash(f"Server '{server_name}' restarted successfully.", "success")
    else:
        flash(
            f"Error restarting server '{server_name}': {response['message']}", "error"
        )
    return redirect(url_for("server_routes.index"))


@server_bp.route("/server/<server_name>/update", methods=["GET", "POST"])
def update_server_route(server_name):
    base_dir = get_base_dir()
    response = handlers.update_server_handler(server_name, base_dir=base_dir)
    if response["status"] == "success":
        flash(f"Server '{server_name}' Updated successfully.", "success")
    else:
        flash(f"Error updating server '{server_name}': {response['message']}", "error")
    return redirect(url_for("server_routes.index"))


@server_bp.route("/install", methods=["GET", "POST"])
def install_server_route():
    if request.method == "POST":
        server_name = request.form["server_name"]
        server_version = request.form["server_version"]

        if not server_name:
            flash("Server name cannot be empty.", "error")
            return render_template("install.html")
        if not server_version:
            flash("Server version cannot be empty.", "error")
            return render_template("install.html", server_name=server_name)
        if ";" in server_name:
            flash("Server name cannot contain semicolons.", "error")
            return render_template("install.html")
        # Validate the format
        validation_result = handlers.validate_server_name_format_handler(server_name)
        if validation_result["status"] == "error":
            flash(validation_result["message"], "error")
            return render_template(
                "install.html", server_name=server_name, server_version=server_version
            )

        base_dir = get_base_dir()
        config_dir = settings.get("CONFIG_DIR")

        # Check if server exists *before* calling the handler.
        server_dir = os.path.join(base_dir, server_name)
        if os.path.exists(server_dir):
            # Render install.html with confirm_delete=True and the server_name.
            return render_template(
                "install.html",
                confirm_delete=True,
                server_name=server_name,
                server_version=server_version,
            )

        # If server doesn't exist, proceed with installation.
        result = handlers.install_new_server_handler(
            server_name, server_version, base_dir, config_dir
        )

        if result["status"] == "error":
            flash(result["message"], "error")
            return render_template(
                "install.html", server_name=server_name, server_version=server_version
            )
        elif result["status"] == "confirm":
            return render_template(
                "install.html",
                confirm_delete=True,
                server_name=result["server_name"],
                server_version=result["server_version"],
            )
        elif result["status"] == "success":
            return redirect(
                url_for(
                    "server_routes.configure_properties_route",
                    server_name=result["server_name"],
                    new_install=True,
                )
            )
        else:
            flash("An unexpected error occurred.", "error")
            return redirect(url_for("server_routes.index"))

    else:  # request.method == 'GET'
        return render_template("install.html")


@server_bp.route("/install/confirm", methods=["POST"])
def confirm_install_route():
    server_name = request.form.get("server_name")
    server_version = request.form.get("server_version")
    confirm = request.form.get("confirm")
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")

    if not server_name or not server_version:
        flash("Missing server name or version.", "error")
        return redirect(url_for("server_routes.index"))

    if confirm == "yes":
        # Delete existing server data.
        delete_result = handlers.delete_server_data_handler(
            server_name, base_dir, config_dir
        )
        if delete_result["status"] == "error":
            flash(
                f"Error deleting existing server data: {delete_result['message']}",
                "error",
            )
            return render_template(
                "install.html", server_name=server_name, server_version=server_version
            )

        # Call install_new_server_handler AGAIN, after deletion.
        install_result = handlers.install_new_server_handler(
            server_name, server_version, base_dir, config_dir
        )

        if install_result["status"] == "error":
            flash(install_result["message"], "error")
            return render_template(
                "install.html", server_name=server_name, server_version=server_version
            )

        elif install_result["status"] == "success":
            return redirect(
                url_for(
                    "server_routes.configure_properties_route",
                    server_name=install_result["server_name"],
                    new_install=True,
                )
            )

        else:
            flash("An unexpected error occurred during installation.", "error")
            return redirect(url_for("server_routes.index"))

    elif confirm == "no":
        flash("Server installation cancelled.", "info")
        return redirect(url_for("server_routes.index"))
    else:
        flash("Invalid confirmation value.", "error")
        return redirect(url_for("server_routes.index"))


@server_bp.route("/server/<server_name>/configure_properties", methods=["GET", "POST"])
def configure_properties_route(server_name):
    base_dir = get_base_dir()
    server_dir = os.path.join(base_dir, server_name)
    server_properties_path = os.path.join(server_dir, "server.properties")

    if not os.path.exists(server_properties_path):
        flash(f"server.properties not found for server: {server_name}", "error")
        return redirect(url_for("server_routes.index"))
    # Check if new_install is True, convert to boolean
    new_install_str = request.args.get(
        "new_install", "False"
    )  # Get as string, default "False"
    new_install = new_install_str.lower() == "true"

    if request.method == "POST":
        # Handle form submission (save properties)
        properties_to_update = {}
        allowed_keys = [
            "server-name",
            "level-name",
            "gamemode",
            "difficulty",
            "allow-cheats",
            "server-port",
            "server-portv6",
            "enable-lan-visibility",
            "allow-list",
            "max-players",
            "default-player-permission-level",
            "view-distance",
            "tick-distance",
            "level-seed",
            "online-mode",
            "texturepack-required",
        ]
        for key in allowed_keys:
            value = request.form.get(key)
            if value is not None:
                if key == "level-name":
                    value = value.replace(" ", "_")
                validation_response = handlers.validate_property_value_handler(
                    key, value
                )
                if validation_response["status"] == "error":
                    flash(validation_response["message"], "error")
                    current_properties = handlers.read_server_properties_handler(
                        server_name, base_dir
                    )["properties"]
                    return render_template(
                        "configure_properties.html",
                        server_name=server_name,
                        properties=current_properties,
                        new_install=new_install,
                    )
                properties_to_update[key] = value
        modify_response = handlers.modify_server_properties_handler(
            server_name, properties_to_update, base_dir
        )
        if modify_response["status"] == "error":
            flash(
                f"Error updating server properties: {modify_response['message']}",
                "error",
            )
            current_properties = handlers.read_server_properties_handler(
                server_name, base_dir
            )["properties"]
            return render_template(
                "configure_properties.html",
                server_name=server_name,
                properties=current_properties,
                new_install=new_install,
            )

        # Write server config
        config_dir = settings.get("CONFIG_DIR")
        write_config_response = handlers.write_server_config_handler(
            server_name, "server_name", server_name, config_dir
        )
        if write_config_response["status"] == "error":
            flash(write_config_response["message"], "error")
        level_name = request.form.get("level-name")
        write_config_response = handlers.write_server_config_handler(
            server_name, "target_version", level_name, config_dir
        )
        if write_config_response["status"] == "error":
            flash(write_config_response["message"], "error")
        write_config_response = handlers.write_server_config_handler(
            server_name, "status", "INSTALLED", config_dir
        )
        if write_config_response["status"] == "error":
            flash(write_config_response["message"], "error")

        flash(f"Server properties for '{server_name}' updated successfully!", "success")

        # Redirect based on new_install flag
        if new_install:
            return redirect(
                url_for(
                    "server_routes.configure_allowlist_route",
                    server_name=server_name,
                    new_install=new_install,
                )
            )
        else:
            return redirect(url_for("server_routes.index"))

    else:  # GET request
        properties_response = handlers.read_server_properties_handler(
            server_name, base_dir
        )
        if properties_response["status"] == "error":
            flash(
                f"Error loading properties: {properties_response['message']}", "error"
            )
            return redirect(url_for("server_routes.index"))

        return render_template(
            "configure_properties.html",
            server_name=server_name,
            properties=properties_response["properties"],
            new_install=new_install,
        )


@server_bp.route("/server/<server_name>/configure_allowlist", methods=["GET", "POST"])
def configure_allowlist_route(server_name):
    base_dir = get_base_dir()
    new_install_str = request.args.get(
        "new_install", "False"
    )  # Get as string, default "False"
    new_install = new_install_str.lower() == "true"

    if request.method == "POST":
        player_names_raw = request.form.get("player_names", "")
        ignore_limit = (
            request.form.get("ignore_limit") == "on"
        )  # Convert checkbox to boolean

        # Process player names (split into a list, remove empty lines)
        player_names = [
            name.strip() for name in player_names_raw.splitlines() if name.strip()
        ]

        new_players_data = []
        for name in player_names:
            new_players_data.append({"name": name, "ignoresPlayerLimit": ignore_limit})

        result = handlers.configure_allowlist_handler(
            server_name, base_dir, new_players_data
        )

        if result["status"] == "success":
            flash(f"Allowlist for '{server_name}' updated successfully!", "success")
            if new_install:
                return redirect(
                    url_for(
                        "server_routes.configure_permissions_route",
                        server_name=server_name,
                        new_install=new_install,
                    )
                )
            else:
                return redirect(url_for("server_routes.index"))
        else:
            flash(f"Error updating allowlist: {result['message']}", "error")
            # Re-render the form with the existing and attempted new players
            return render_template(
                "configure_allowlist.html",
                server_name=server_name,
                existing_players=result.get("existing_players", []),
                new_install=new_install,
            )

    else:  # GET request
        result = handlers.configure_allowlist_handler(server_name, base_dir)
        if result["status"] == "error":
            flash(f"Error loading allowlist: {result['message']}", "error")
            return redirect(url_for("server_routes.index"))

        existing_players = result.get("existing_players", [])  # Default to empty list
        return render_template(
            "configure_allowlist.html",
            server_name=server_name,
            existing_players=existing_players,
            new_install=new_install,
        )


@server_bp.route("/server/<server_name>/configure_permissions", methods=["GET", "POST"])
def configure_permissions_route(server_name):
    base_dir = get_base_dir()
    new_install_str = request.args.get("new_install", "False")
    new_install = new_install_str.lower() == "true"

    if request.method == "POST":
        # Handle form submission (save permissions)
        permissions_data = {}
        for xuid, permission in request.form.items():
            if permission.lower() not in ("visitor", "member", "operator"):
                flash(f"Invalid permission level for XUID {xuid}: {permission}", "error")
                return redirect(
                    url_for(
                        "server_routes.configure_permissions_route",
                        server_name=server_name,
                        new_install=new_install
                    )
                )

            permissions_data[xuid] = permission.lower()

        players_response = handlers.get_players_from_json_handler()
        if players_response["status"] == "error":
             # We still want to continue even if we cannot load player names.
            player_names = {} # Just use an empty dict.

        else:
            player_names = {
                player["xuid"]: player["name"] for player in players_response["players"]
            }

        for xuid, permission in permissions_data.items():
            player_name = player_names.get(xuid, "Unknown Player")
            result = handlers.configure_player_permission_handler(
                server_name, xuid, player_name, permission, base_dir
            )
            if result["status"] == "error":
                flash(f"Error setting permission for {player_name}: {result['message']}", "error")
                # Continue to the next player, even on error

        flash(f"Permissions for server '{server_name}' updated.", "success")
        if new_install:
            return redirect(url_for('server_routes.configure_service_route', server_name=server_name, new_install=new_install))
        return redirect(url_for("server_routes.index"))


    else:  # GET request
        players_response = handlers.get_players_from_json_handler()
        if players_response["status"] == "error":
            # Instead of redirecting, flash a message and continue rendering the template.
            flash(f"Error loading player data: {players_response['message']}.  No players found.", "warning")
            players = []  # Provide an empty list so the template doesn't break.
        else:
            players = players_response["players"]


        permissions = {}
        try:
            server_dir = os.path.join(base_dir, server_name)
            permissions_file = os.path.join(server_dir, "permissions.json")
            if os.path.exists(permissions_file):
                with open(permissions_file, "r") as f:
                    permissions_data = json.load(f)
                    for player_entry in permissions_data:
                        permissions[player_entry["xuid"]] = player_entry["permission"]
        except (OSError, json.JSONDecodeError) as e:
            flash(f"Error reading permissions.json: {e}", "error")

        return render_template(
            "configure_permissions.html",
            server_name=server_name,
            players=players,
            permissions=permissions,
            new_install=new_install,
        )


@server_bp.route("/server/<server_name>/configure_service", methods=["GET", "POST"])
def configure_service_route(server_name):
    base_dir = get_base_dir()
    new_install_str = request.args.get("new_install", "False")
    new_install = new_install_str.lower() == "true"
    if request.method == "POST":
        if platform.system() == "Linux":
            autoupdate = request.form.get("autoupdate") == "on"
            autostart = request.form.get("autostart") == "on"
            response = handlers.create_systemd_service_handler(
                server_name, base_dir, autoupdate, autostart
            )
            if response["status"] == "error":
                flash(response["message"], "error")
                # Re-render the form with current values
                return render_template(
                    "configure_service.html",
                    server_name=server_name,
                    os=platform.system(),
                    autoupdate=autoupdate,
                    autostart=autostart,
                    new_install=new_install,
                )

        elif platform.system() == "Windows":
            autoupdate = request.form.get("autoupdate") == "on"
            response = handlers.set_windows_autoupdate_handler(
                server_name, "true" if autoupdate else "false"
            )  # Convert boolean to string
            if response["status"] == "error":
                flash(response["message"], "error")
                # Re-render the form
                return render_template(
                    "configure_service.html",
                    server_name=server_name,
                    os=platform.system(),
                    autoupdate=autoupdate,
                    new_install=new_install,
                )
        else:
            flash("Unsupported operating system for service configuration.", "error")
            return redirect(url_for("server_routes.index"))

        flash(f"Service settings for '{server_name}' updated successfully!", "success")

        # Check if we should start the server
        if new_install:
            if request.form.get("start_server") == "on":  # Check if checkbox is checked
                start_result = handlers.start_server_handler(server_name, base_dir)
                if start_result["status"] == "error":
                    flash(f"Error starting server: {start_result['message']}", "error")
                    #  Even if start fails, continue to index.  User can start manually.
                else:
                    flash(f"Server '{server_name}' started.", "success")
            return redirect(url_for("server_routes.index"))
        return redirect(url_for("server_routes.index"))

    else:  # GET request
        if platform.system() == "Linux":
            # For Linux, we don't need to pre-populate any values. systemd handles it.
            return render_template(
                "configure_service.html",
                server_name=server_name,
                os=platform.system(),
                new_install=new_install,
            )
        elif platform.system() == "Windows":
            # Get current autoupdate setting from config.json
            config_dir = settings.get("CONFIG_DIR")
            autoupdate_value = server_base.manage_server_config(
                server_name, "autoupdate", "read", config_dir=config_dir
            )
            # Convert config value to boolean for checkbox
            autoupdate = autoupdate_value == "true" if autoupdate_value else False
            return render_template(
                "configure_service.html",
                server_name=server_name,
                os=platform.system(),
                autoupdate=autoupdate,  # Pass the boolean value
                new_install=new_install,
            )
        else:
            flash("Unsupported operating system for service configuration.", "error")
            return redirect(url_for("server_routes.index"))
