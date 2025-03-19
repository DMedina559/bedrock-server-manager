# bedrock-server-manager/bedrock_server_manager/web/routes/server_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from bedrock_server_manager import handlers
from bedrock_server_manager.utils.general import get_base_dir
from bedrock_server_manager.config.settings import settings
import os

server_bp = Blueprint("server_routes", __name__)  # Create a blueprint


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
        # Validate
        if not server_name:
            flash("Server name cannot be empty.", "error")
            return render_template("install.html")
        if not server_version:
            flash("Server version cannot be empty.", "error")
            return render_template("install.html", server_name=server_name)
        if ";" in server_name:
            flash("Server name cannot contain semicolons.", "error")
            return render_template("install.html")
        validation_result = handlers.validate_server_name_format_handler(server_name)
        if validation_result["status"] == "error":
            flash(validation_result["message"], "error")
            return render_template(
                "install.html", server_name=server_name, server_version=server_version
            )

        base_dir = get_base_dir()
        config_dir = settings.get("CONFIG_DIR")
        server_dir = os.path.join(base_dir, server_name)

        # Check if server exists *before* calling the handler
        if os.path.exists(server_dir):
            # Render install.html with confirm_delete=True and server details
            return render_template(
                "install.html",
                confirm_delete=True,
                server_name=server_name,
                server_version=server_version,
            )

        # If server doesn't exist, proceed with installation
        result = handlers.install_new_server_handler(
            server_name, server_version, base_dir, config_dir
        )

        if result["status"] == "error":
            flash(result["message"], "error")
            return render_template(
                "install.html", server_name=server_name, server_version=server_version
            )
        elif result["status"] == "success":
            return redirect(
                url_for(
                    "server_routes.configure_properties_route",
                    server_name=result["server_name"],
                )
            )
        else:
            flash("An unexpected error occurred.", "error")
            return redirect(url_for("server_routes.index"))

    else:  # request.method == 'GET'
        return render_template("install.html")


@server_bp.route("/install/confirm", methods=["POST"])
def confirm_install_route():
    server_name = request.form.get("server_name")  # Get server_name from form
    server_version = request.form.get("server_version")
    confirm = request.form.get("confirm")  # Get confirmation value (yes/no)
    base_dir = get_base_dir()
    config_dir = settings.get("CONFIG_DIR")

    if not server_name or not server_version:
        flash("Missing server name or version.", "error")
        return redirect(url_for("server_routes.index"))

    if confirm == "yes":
        # Delete existing server data
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
            # Redirect to configure_properties_route with server_name
            return redirect(
                url_for(
                    "server_routes.configure_properties_route",
                    server_name=install_result["server_name"],
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


@server_bp.route("/server/<server_name>/configure", methods=["GET", "POST"])
def configure_properties_route(server_name):
    base_dir = get_base_dir()

    # Validate server name format (using handler)
    validation_response = handlers.validate_server_name_format_handler(server_name)
    if validation_response["status"] == "error":
        flash(validation_response["message"], "error")
        return redirect(url_for("server_routes.index"))

    if request.method == "POST":
        # Handle form submission (save properties)
        properties_to_update = {}

        # List of allowed keys
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

        # Iterate through allowed keys, get values, and validate
        for key in allowed_keys:
            value = request.form.get(key)  # Use .get()
            if value is not None:  # Key exists in form.
                if key == "level-name":  # special case
                    value = value.replace(" ", "_")

                validation_response = handlers.validate_property_value_handler(
                    key, value
                )
                if validation_response["status"] == "error":
                    flash(validation_response["message"], "error")
                    # Re-render form WITH existing, and current properties
                    current_properties = handlers.read_server_properties_handler(
                        server_name, base_dir
                    )["properties"]
                    return render_template(
                        "configure_properties.html",
                        server_name=server_name,
                        properties=current_properties,
                    )
                properties_to_update[key] = value

        # Call the handler to modify properties
        modify_response = handlers.modify_server_properties_handler(
            server_name, properties_to_update, base_dir
        )
        if modify_response["status"] == "error":
            flash(
                f"Error updating server properties: {modify_response['message']}",
                "error",
            )
            # Re-render form with current values
            current_properties = handlers.read_server_properties_handler(
                server_name, base_dir
            )["properties"]
            return render_template(
                "configure_properties.html",
                server_name=server_name,
                properties=current_properties,
            )
        # Write server config
        config_dir = settings.get("CONFIG_DIR")
        write_config_response = handlers.write_server_config_handler(
            server_name, "server_name", server_name, config_dir
        )
        if write_config_response["status"] == "error":
            flash(write_config_response["message"], "error")
        level_name = request.form.get("level-name")  # Get from form
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

        # Call handler
        # create_service_result = handlers.create_service_handler(server_name,base_dir)
        # if create_service_result["status"] == "error":
        #    flash(f"Failed to create service: {create_service_result['message']}", 'error')
        flash(f"Server properties for '{server_name}' updated successfully!", "success")
        return redirect(url_for("server_routes.index"))
    else:
        # Load and pass existing properties (using handler)
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
        )
