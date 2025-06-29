# bedrock_server_manager/web/utils/auth_decorators.py
"""
Decorators for handling authentication and authorization in the Flask web application.

Provides mechanisms to protect view functions, requiring either a valid JWT
or an active Flask session, and includes CSRF protection for session-based requests.
"""

import functools
import logging
from typing import Callable, Optional

# Third-party imports
from flask import (
    session,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    Response,
    g,
)
from flask_jwt_extended import (
    verify_jwt_in_request,
    get_jwt_identity,
)
from flask_wtf.csrf import validate_csrf, CSRFError

logger = logging.getLogger(__name__)


def auth_required(view: Callable) -> Callable:
    """
    Decorator enforcing authentication (JWT or Session + CSRF).

    Determines the user identity and stores it in flask.g.user_identity
    before calling the decorated view.
    """

    @functools.wraps(view)
    def wrapped_view(*args, **kwargs) -> Response:
        identity: Optional[str] = None
        auth_method: Optional[str] = None
        auth_error: Optional[Exception] = None
        g.user_identity = None  # Initialize in request context

        logger.debug(
            f"Auth required check initiated for path: {request.path} [{request.method}]"
        )

        # --- 1. Attempt JWT Authentication ---
        try:
            # verify_jwt_in_request(optional=True) # Changed to non-optional for debugging
            verify_jwt_in_request()  # Non-optional: will raise error if no valid JWT in configured locations
            identity = (
                get_jwt_identity()
            )  # Should retrieve identity if verify_jwt_in_request passed

            if identity:
                g.user_identity = identity
                logger.debug(
                    f"Auth successful via JWT for identity '{identity}'. Stored in g."
                )
                return view(*args, **kwargs)
            else:

                logger.warning(
                    f"JWT verified but no identity obtained for path {request.path}. This is unexpected."
                )
                auth_error = Exception(
                    "JWT verified but no identity found."
                )  # Create a generic error for logging below

        except (
            Exception
        ) as e_jwt_verify:  # Catch specific JWT errors if possible, or broad Exception
            logger.error(
                f"JWT Verification explicit error for path {request.path}: {e_jwt_verify}",
                exc_info=True,
            )
            auth_error = (
                e_jwt_verify  # Store the error for logging in the failure message
            )
            identity = None  # Ensure identity is None if verification fails

        # If identity (now g.user_identity) is not set after JWT check, then authentication has failed.
        if not g.user_identity:
            log_message = f"Authentication failed for path '{request.path}'."
            if auth_error:  # This auth_error would be from the exception block above
                log_message += f" Reason: JWT Error - {type(auth_error).__name__}: {str(auth_error)}"
            else:
                log_message += " No valid JWT found."
            logger.warning(log_message)

            best_match = request.accept_mimetypes.best_match(
                ["application/json", "text/html"]
            )
            prefers_html = (
                best_match == "text/html"
                and request.accept_mimetypes[best_match]
                > request.accept_mimetypes["application/json"]
            )

            if prefers_html:  # Typically for UI page GET requests
                flash("Please log in to access this page.", "warning")
                login_url = url_for("auth.login", next=request.url)
                logger.debug(f"Redirecting browser-like client to login: {login_url}")
                return redirect(login_url)
            else:  # Typically for API calls
                logger.debug(
                    "Returning 401 JSON response for API-like client due to missing/invalid JWT."
                )
                return (
                    jsonify(
                        error="Unauthorized",
                        message="Authentication token is required and was not found or is invalid.",
                    ),
                    401,
                )

        if auth_error:
            log_message += f" Reason: {type(auth_error).__name__}"
        else:
            log_message += " No valid JWT or session found."
        logger.warning(log_message)

        best_match = request.accept_mimetypes.best_match(
            ["application/json", "text/html"]
        )
        prefers_html = (
            best_match == "text/html"
            and request.accept_mimetypes[best_match]
            > request.accept_mimetypes["application/json"]
        )

        if prefers_html:
            flash("Please log in to access this page.", "warning")
            login_url = url_for("auth.login", next=request.url)
            logger.debug(f"Redirecting browser-like client to login: {login_url}")
            return redirect(login_url)
        else:
            logger.debug("Returning 401 JSON response for API-like client.")
            return (
                jsonify(error="Unauthorized", message="Authentication required."),
                401,
            )

    return wrapped_view


def get_current_identity() -> Optional[str]:
    """
    Retrieves the identity of the currently authenticated user,
    as determined by the @auth_required decorator and stored in flask.g.

    Returns:
        The identity string (e.g., username or JWT subject) if authenticated
        during the current request, otherwise None.
    """
    identity = getattr(g, "user_identity", None)
    if identity:
        logger.debug(f"Retrieved identity from g: {identity}")
        return identity
    else:
        # This case should ideally not happen if @auth_required is used correctly,
        # but provides a fallback message if called unexpectedly.
        logger.warning(
            "get_current_identity called but no identity found in flask.g. Was @auth_required used?"
        )
        return None
