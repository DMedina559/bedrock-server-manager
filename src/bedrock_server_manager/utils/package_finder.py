# bedrock_server_manager/utils/package_finder.py
"""
Utility function to locate the installed executable path for a given package.

Handles complexities arising from virtual environments and different
installation schemes (system-wide, user).
"""

import importlib.metadata
import logging
import platform
import site
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def find_executable(  # noqa: C901
    package_name: str, executable_name: Optional[str] = None
) -> Optional[Path]:
    """
    Dynamically finds the path to an executable script installed by a package.

    This function attempts to locate the executable by:
    1. Getting package distribution metadata.
    2. If `executable_name` is not provided, finding it from the package's
       'console_scripts' entry points (if exactly one exists).
    3. Checking the standard script location within the active virtual environment
       (sys.prefix / 'bin' or sys.prefix / 'Scripts').
    4. If not found or not in a venv, searching common script locations relative
       to system and user site-packages directories.

    Args:
        package_name: The name of the installed package (e.g., 'bedrock-server-manager').
        executable_name: The name of the executable script (e.g., 'bedrock-server-manager').
                         If None, the function tries to find a unique 'console_scripts'
                         entry point.

    Returns:
        A Path object pointing to the found executable file, or None if the package
        or executable cannot be located.
    """
    logger.debug(
        f"Attempting to find executable for package '{package_name}' (executable name: {executable_name or 'auto-detect'})"
    )

    # Determine executable suffix for Windows
    exe_suffix = ".exe" if platform.system() == "Windows" else ""

    # 1. Find the package distribution
    try:
        distribution = importlib.metadata.distribution(package_name)
        logger.debug(
            f"Found distribution: {distribution.metadata['Name']} v{distribution.version}"
        )
    except importlib.metadata.PackageNotFoundError:
        logger.warning(
            f"Package '{package_name}' metadata not found. Cannot locate executable."
        )
        return None

    # 2. Determine the executable name if not provided
    if executable_name is None:
        try:
            entry_points = distribution.entry_points
            console_scripts = [
                ep for ep in entry_points if ep.group == "console_scripts"
            ]

            if not console_scripts:
                logger.warning(
                    f"No 'console_scripts' entry points found for package '{package_name}'. Cannot auto-detect executable."
                )
                return None
            if len(console_scripts) > 1:
                logger.warning(
                    f"Multiple 'console_scripts' entry points found for '{package_name}'. "
                    f"Please specify the desired 'executable_name' argument."
                )
                for ep in console_scripts:
                    logger.info(f"  - Found entry point: {ep.name}")
                return None  # Ambiguous case

            executable_name = console_scripts[0].name
            logger.debug(
                f"Auto-detected executable name from entry point: '{executable_name}'"
            )
        except Exception as e:
            logger.error(
                f"Error processing entry points for '{package_name}': {e}",
                exc_info=True,
            )
            return None

    # Construct the full executable name with potential suffix
    full_executable_name = f"{executable_name}{exe_suffix}"

    # 3. Check Virtual Environment Location
    # sys.prefix points to the active environment path (venv or system Python)
    # sys.base_prefix points to the system Python even inside a venv
    if sys.prefix != sys.base_prefix:
        logger.debug(f"Detected virtual environment at: {sys.prefix}")
        if platform.system() == "Windows":
            bin_dir = Path(sys.prefix) / "Scripts"
        else:
            bin_dir = Path(sys.prefix) / "bin"

        executable_path = bin_dir / full_executable_name
        logger.debug(f"Checking virtual environment script path: {executable_path}")
        if executable_path.exists() and executable_path.is_file():
            logger.info(f"Executable found in virtual environment: {executable_path}")
            return executable_path
        else:
            logger.debug(
                f"Executable not found at virtual environment path: {executable_path}"
            )
            # Continue searching site-packages as a fallback, sometimes installs can be odd

    # 4. Check System/User Site-Packages Locations
    # This is a fallback or the primary method if not in a virtual env.
    logger.debug("Checking locations relative to site-packages directories.")
    search_dirs = []
    system_site_packages = site.getsitepackages()
    if system_site_packages:
        logger.debug(f"System site-packages: {system_site_packages}")
        search_dirs.extend(system_site_packages)

    # Add user site-packages if available and different from system paths
    if hasattr(site, "getusersitepackages"):
        user_site_packages = site.getusersitepackages()
        if user_site_packages and user_site_packages not in search_dirs:
            logger.debug(f"User site-packages: {user_site_packages}")
            search_dirs.append(user_site_packages)

    # Heuristic: Check 'bin'/'Scripts' dirs relative to site-packages paths.
    # This covers common structures like /usr/lib/pythonX.Y/site-packages and /usr/local/lib/pythonX.Y/dist-packages
    # where the corresponding bin is often /usr/bin or /usr/local/bin, or sibling 'Scripts' on Windows.
    # This part can be less reliable than the venv check.
    potential_bin_dirs = set()  # Use set to avoid duplicates
    for site_path_str in search_dirs:
        site_path = Path(site_path_str)
        if not site_path.is_dir():
            logger.debug(f"Skipping non-existent site-packages path: {site_path}")
            continue

        # Common locations relative to a site-packages directory:
        # - Windows: Often ..\Scripts or ..\..\PythonXY\Scripts
        # - Linux/macOS: Often ../bin, ../../bin, /usr/local/bin, /usr/bin
        if platform.system() == "Windows":
            script_dir_name = "Scripts"
            # Check relative paths first (common for user installs/some structures)
            potential_bin_dirs.add(site_path.parent / script_dir_name)
            potential_bin_dirs.add(site_path.parent.parent / script_dir_name)
            # Also consider system Python scripts dir directly if applicable
            if sys.base_prefix:  # If we know the base Python install dir
                potential_bin_dirs.add(Path(sys.base_prefix) / script_dir_name)
        else:
            script_dir_name = "bin"
            # Check relative paths
            potential_bin_dirs.add(site_path.parent / script_dir_name)
            potential_bin_dirs.add(site_path.parent.parent / script_dir_name)
            # Common absolute paths (less reliable, but worth checking)
            potential_bin_dirs.add(Path("/usr/local") / script_dir_name)
            potential_bin_dirs.add(Path("/usr") / script_dir_name)
            # Also consider system Python bin dir directly if applicable
            if sys.base_prefix:  # If we know the base Python install dir
                potential_bin_dirs.add(Path(sys.base_prefix) / script_dir_name)

    logger.debug(
        f"Potential script directories to check: {sorted(list(potential_bin_dirs))}"
    )

    for bin_dir in sorted(list(potential_bin_dirs)):  # Check in a consistent order
        if not bin_dir.is_dir():
            continue  # Skip if the potential directory doesn't exist

        executable_path = bin_dir / full_executable_name
        logger.debug(f"Checking site-related path: {executable_path}")
        if executable_path.exists() and executable_path.is_file():
            logger.info(f"Executable found via site-packages search: {executable_path}")
            return executable_path

    # 5. Not Found
    logger.warning(
        f"Executable '{full_executable_name}' for package '{package_name}' could not be found in any checked locations."
    )
    return None
