# bedrock_server_manager/web/routes/auth_routes.py
"""
Flask Blueprint for handling user authentication.

Provides routes for:
- Web UI login page (GET).
- API login (JWT-based) expecting JSON credentials (POST).
- User logout (clears session and advises client to clear JWT).
"""
import functools
import logging
from enum import Enum, auto
from typing import Callable

# Third-party imports
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    current_app,
    jsonify,
    Response,
)
from werkzeug.security import check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length
from flask_jwt_extended import create_access_token, JWTManager

# Local imports
from bedrock_server_manager.config.const import env_name
from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
)

logger = logging.getLogger(__name__)

# --- Blueprint and Extension Setup ---
auth_bp = Blueprint(
    "auth",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)
jwt = JWTManager()


# --- Forms ---
class LoginForm(FlaskForm):
    """Login form definition using Flask-WTF."""

    class Meta:
        csrf = False

    username = StringField(
        "Username",
        validators=[
            DataRequired(message="Username is required."),
            Length(min=1, max=80),
        ],
        render_kw={"autocomplete": "username"},
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Password is required.")],
        render_kw={"autocomplete": "current-password"},
    )


# --- Centralized Authentication Logic ---
class AuthResult(Enum):
    SUCCESS = auto()
    INVALID_CREDENTIALS = auto()
    SERVER_CONFIG_ERROR = auto()


def _validate_credentials(username_attempt: str, password_attempt: str) -> AuthResult:
    username_env = f"{env_name}_USERNAME"
    password_env = f"{env_name}_PASSWORD"
    expected_username = current_app.config.get(username_env)
    stored_password_hash = current_app.config.get(password_env)

    if not expected_username or not stored_password_hash:
        logger.critical(
            f"Server authentication configuration error: '{username_env}' or '{password_env}' not set."
        )
        return AuthResult.SERVER_CONFIG_ERROR
    if username_attempt != expected_username:
        return AuthResult.INVALID_CREDENTIALS
    try:
        if check_password_hash(stored_password_hash, password_attempt):
            return AuthResult.SUCCESS
    except Exception as hash_err:
        logger.error(
            f"Error during password hash check (is '{password_env}' a valid hash?): {hash_err}",
            exc_info=True,
        )
    return AuthResult.INVALID_CREDENTIALS


# --- Web UI Login Page Route (GET only) ---
@auth_bp.route("/login", methods=["GET"])
def login() -> Response:
    """Serves the login page. Authentication is handled via JS calling /api/login."""
    if session.get("logged_in"):
        logger.debug("User already has an active session, redirecting to dashboard.")
        return redirect(url_for("main_routes.index"))
    form = LoginForm()
    return render_template("login.html", form=form)


# --- API Login Route (POST) ---
@auth_bp.route("/api/login", methods=["POST"])
def api_login() -> Response:
    """Handles API user login (JWT-based)."""
    if not request.is_json:
        return jsonify(status="error", message="Request must be JSON"), 400
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return (
            jsonify(status="error", message="Missing username or password parameter"),
            400,
        )

    logger.info(f"API login attempt for '{username}' from {request.remote_addr}")
    auth_result = _validate_credentials(username, password)

    if auth_result == AuthResult.SUCCESS:
        access_token = create_access_token(identity=username)
        session["logged_in"] = True
        session["username"] = username
        logger.info(
            f"API login successful for '{username}'. JWT issued and Flask session set."
        )
        return (
            jsonify(
                status="success",
                access_token=access_token,
                message="Login successful! Redirecting...",
            ),
            200,
        )
    elif auth_result == AuthResult.SERVER_CONFIG_ERROR:
        return (
            jsonify(
                status="error", message="Server configuration error prevents login."
            ),
            500,
        )
    else:
        logger.warning(
            f"Invalid API login attempt for '{username}' from {request.remote_addr}."
        )
        return jsonify(status="error", message="Bad username or password"), 401


# --- Logout Route ---
@auth_bp.route("/logout")
@auth_required
def logout() -> Response:
    """
    Logs the user out by clearing the Flask session and advising client to clear JWT.
    Client-side JavaScript should handle clearing localStorage/sessionStorage for 'jwt_token'.
    """
    username = session.get("username", "Unknown user")
    session.pop("logged_in", None)
    session.pop("username", None)
    logger.info(f"User '{username}' Flask session cleared from {request.remote_addr}.")

    flash("You have been successfully logged out.", "info")

    return redirect(url_for("auth.login"))
