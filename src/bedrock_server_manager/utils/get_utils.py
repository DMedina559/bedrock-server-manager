# bedrock_server_manager/bedrock_server_manager/utils/get_utils.py
"""
Provides utility helper functions for gettings various variables.
"""

import platform
import logging
import random
from typing import Optional

# Local imports
from bedrock_server_manager.config.splash_text import SPLASH_TEXTS
from bedrock_server_manager.error import SystemError

logger = logging.getLogger(__name__)

# --- Helper Functions ---


def _get_splash_text() -> str:
    """
    Selects and returns a random splash text message.

    Pulls from the SPLASH_TEXTS constant defined in 'splash_text.py'.
    Handles cases where SPLASH_TEXTS might be a dictionary of lists, a simple list/tuple,
    empty, or not defined.

    Returns:
        A randomly chosen splash text string, or a fallback message if none can be selected.
    """
    fallback_splash: str = "Amazing Error Handling!"
    chosen_splash: str = fallback_splash

    try:
        # Check if SPLASH_TEXTS is defined and accessible
        if "SPLASH_TEXTS" not in globals() and "SPLASH_TEXTS" not in locals():
            logger.warning(
                "Context Helper: SPLASH_TEXTS constant not found or not imported."
            )
            return fallback_splash  # Return fallback if constant isn't available

        all_texts = []
        if isinstance(SPLASH_TEXTS, dict) and SPLASH_TEXTS:
            # If it's a dictionary, flatten all its list/tuple values into one list
            for category_list in SPLASH_TEXTS.values():
                if isinstance(category_list, (list, tuple)):
                    all_texts.extend(category_list)
            logger.debug("Context Helper: Processing SPLASH_TEXTS as dictionary.")
        elif isinstance(SPLASH_TEXTS, (list, tuple)) and SPLASH_TEXTS:
            # If it's already a list or tuple, use it directly
            all_texts = list(SPLASH_TEXTS)  # Ensure it's a list for consistency
            logger.debug("Context Helper: Processing SPLASH_TEXTS as list/tuple.")
        else:
            logger.debug(
                f"Context Helper: SPLASH_TEXTS is empty or has an unexpected type ({type(SPLASH_TEXTS)}). Using fallback."
            )
            # all_texts remains empty, will use fallback

        if all_texts:
            chosen_splash = random.choice(all_texts)
        else:
            # Log if we had the constant but it resulted in no usable texts
            if "SPLASH_TEXTS" in globals() or "SPLASH_TEXTS" in locals():
                logger.debug(
                    "Context Helper: No valid splash texts found after processing SPLASH_TEXTS constant. Using fallback."
                )
            # Otherwise, the warning about the constant not being found was already logged.
            chosen_splash = fallback_splash  # Ensure fallback if list is empty

    except NameError:
        # This case should be caught by the initial check, but kept for safety
        logger.warning(
            "Context Helper: SPLASH_TEXTS constant is not defined (NameError)."
        )
        chosen_splash = fallback_splash
    except Exception as e:
        logger.exception(
            f"Context Helper: Error choosing splash text: {e}", exc_info=True
        )
        chosen_splash = "Error retrieving splash!"  # Fallback indicating an error state

    logger.debug(f"Context Helper: Selected splash text: '{chosen_splash}'")
    return chosen_splash


def get_operating_system_type() -> str:
    """
    Retrieves the operating system type.

    Returns:
        A string representing the OS type (e.g., "Linux", "Windows", "Darwin").

    Raises:
        SystemError: If the OS type cannot be determined (highly unlikely).
    """
    try:
        os_type = platform.system()
        if not os_type:
            # This case is extremely rare with platform.system()
            raise SystemError("Could not determine operating system type.")
        logger.debug(f"Core: Determined OS Type: {os_type}")
        return os_type
    except Exception as e:
        logger.error(f"Core: Error getting OS type: {e}", exc_info=True)
        # Re-raise as a custom error or handle differently if preferred
        raise SystemError(f"Failed to get OS type: {e}")
