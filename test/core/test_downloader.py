# Test cases for bedrock_server_manager.core.downloader
import pytest
import os
import json
import zipfile
import shutil
import logging
import platform  # Added platform import
from pathlib import Path
from unittest import (
    mock,
)  # Will use pytest-mock which provides the 'mocker' fixture, but mock can be useful too.

# Imports from the application
from bedrock_server_manager.core.downloader import (
    BedrockDownloader,
    prune_old_downloads,
)
from bedrock_server_manager.config.settings import Settings
from bedrock_server_manager.error import (
    DownloadError,
    ExtractError,
    MissingArgumentError,
    InternetConnectivityError,
    FileOperationError,
    AppFileNotFoundError,
    ConfigurationError,
    UserInputError,
    SystemError,
)

# For mocking requests
import requests


# --- Fixtures ---


@pytest.fixture
def mock_settings(mocker):
    """Mocks the Settings object to provide controlled configuration values."""
    settings = mocker.MagicMock(spec=Settings)
    # Provide default values for settings typically used by BedrockDownloader
    # These can be overridden in specific tests if needed
    settings.get.side_effect = lambda key, default=None: {
        "paths.downloads": str(
            Path("dummy_downloads")
        ),  # Default, will be overridden by temp_download_base_dir in downloader_instance
        "retention.downloads": 3,
        "_app_name": "TestBSM",
    }.get(key, default)
    return settings


@pytest.fixture
def temp_server_dir(tmp_path_factory):
    """Creates a temporary directory for a server installation."""
    return tmp_path_factory.mktemp("server_dir_")


@pytest.fixture
def temp_download_base_dir(tmp_path_factory):
    """Creates a temporary base directory for downloads."""
    return tmp_path_factory.mktemp("download_base_dir_")


@pytest.fixture
def downloader_instance(mock_settings, temp_server_dir, temp_download_base_dir, mocker):
    """Creates a BedrockDownloader instance with mocked settings and temp paths."""

    # Override the default "paths.downloads" from mock_settings to use the temp directory
    def settings_get_side_effect(key, default=None):
        if key == "paths.downloads":
            return str(temp_download_base_dir)
        return {"retention.downloads": 3, "_app_name": "TestBSM"}.get(key, default)

    mock_settings.get.side_effect = settings_get_side_effect

    # Mock platform.system() by default for predictable behavior, can be overridden in tests
    mocker.patch("platform.system", return_value="Linux")

    downloader = BedrockDownloader(
        settings_obj=mock_settings,
        server_dir=str(temp_server_dir),
        target_version="LATEST",  # Default, can be changed in tests by re-init or new instance
    )
    return downloader


# --- Helper Functions ---


def create_dummy_zip(zip_path: Path, file_list: dict = None):
    """Creates a dummy ZIP file with specified content.

    Args:
        zip_path (Path): The path where the ZIP file will be created.
        file_list (dict, optional): A dictionary where keys are filenames (including paths
                                    within the zip) and values are their content (bytes).
                                    Defaults to a simple dummy file.
    """
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if file_list is None:
        file_list = {"dummy_file.txt": b"This is a dummy file."}

    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in file_list.items():
            zf.writestr(name, content)


# Example basic structure for a test - these will be removed or replaced by actual tests
def test_example_downloader(downloader_instance):
    assert downloader_instance is not None


# --- Tests for prune_old_downloads ---


def create_dummy_files_with_timestamps(
    base_dir: Path, count: int, prefix: str = "bedrock-server-", suffix: str = ".zip"
):
    """Creates dummy files with slightly different modification times."""
    files = []
    for i in range(count):
        file_path = (
            base_dir / f"{prefix}{1 + (i * 0.01)}-{i}{suffix}"
        )  # Ensure unique names and somewhat ordered
        file_path.write_text(f"content_{i}")
        # Set modification time explicitly if needed, though creation order often suffices for tests
        # os.utime(file_path, (time.time() - (count - i) * 3600, time.time() - (count - i) * 3600))
        files.append(file_path)
    # Ensure files are sorted by actual mtime for test predictability if os.utime is used.
    # For this basic version, creation order should be fine if done quickly.
    # To be very robust, sort by name for now if not using explicit os.utime.
    files.sort(key=lambda p: p.name)  # Sort by name to simulate age for this test
    # To make it truly by age, the oldest file should have the earliest timestamp.
    # Let's adjust creation slightly or rely on test structure for specific age tests.
    # For now, let's ensure the files are created with a slight delay to guarantee mtime order
    # For simplicity in this example, we'll use name sorting as a proxy for age in basic cases,
    # but for rigorous age testing, explicit os.utime is better.
    # Re-creating with a slight delay for mtime difference:
    for i, f_path in enumerate(
        files
    ):  # Re-touch files to ensure mtime order based on loop
        os.utime(
            f_path, (Path.stat(f_path).st_atime, Path.stat(f_path).st_mtime + i * 0.1)
        )

    # Re-fetch and sort by actual mtime
    files = list(base_dir.glob(f"{prefix}*{suffix}"))
    files.sort(key=lambda p: p.stat().st_mtime)
    return files


def test_prune_more_files_than_keep(temp_download_base_dir: Path):
    """Test pruning when more files exist than download_keep."""
    prune_dir = temp_download_base_dir / "prune_test_more"
    prune_dir.mkdir(parents=True, exist_ok=True)

    num_files_to_create = 5
    download_keep = 2

    created_files = create_dummy_files_with_timestamps(prune_dir, num_files_to_create)
    assert len(list(prune_dir.glob("*.zip"))) == num_files_to_create

    prune_old_downloads(str(prune_dir), download_keep)

    remaining_files = sorted(
        list(prune_dir.glob("*.zip")), key=lambda p: p.stat().st_mtime
    )
    assert len(remaining_files) == download_keep

    # Verify that the newest files are kept (those at the end of 'created_files' list)
    expected_kept_filenames = {f.name for f in created_files[-download_keep:]}
    remaining_filenames = {f.name for f in remaining_files}
    assert remaining_filenames == expected_kept_filenames


def test_prune_fewer_files_than_keep(temp_download_base_dir: Path):
    """Test pruning when fewer files exist than download_keep."""
    prune_dir = temp_download_base_dir / "prune_test_fewer"
    prune_dir.mkdir(parents=True, exist_ok=True)

    num_files_to_create = 2
    download_keep = 5
    create_dummy_files_with_timestamps(prune_dir, num_files_to_create)

    prune_old_downloads(str(prune_dir), download_keep)

    remaining_files = list(prune_dir.glob("*.zip"))
    assert len(remaining_files) == num_files_to_create  # No files should be deleted


def test_prune_equal_files_to_keep(temp_download_base_dir: Path):
    """Test pruning when the number of files equals download_keep."""
    prune_dir = temp_download_base_dir / "prune_test_equal"
    prune_dir.mkdir(parents=True, exist_ok=True)

    num_files_to_create = 3
    download_keep = 3
    create_dummy_files_with_timestamps(prune_dir, num_files_to_create)

    prune_old_downloads(str(prune_dir), download_keep)

    remaining_files = list(prune_dir.glob("*.zip"))
    assert len(remaining_files) == num_files_to_create


def test_prune_keep_zero_deletes_all(temp_download_base_dir: Path):
    """Test that download_keep = 0 deletes all matching files."""
    prune_dir = temp_download_base_dir / "prune_test_keep_zero"
    prune_dir.mkdir(parents=True, exist_ok=True)

    create_dummy_files_with_timestamps(prune_dir, 3)
    assert len(list(prune_dir.glob("*.zip"))) == 3

    prune_old_downloads(str(prune_dir), 0)

    remaining_files = list(prune_dir.glob("*.zip"))
    assert len(remaining_files) == 0


def test_prune_download_dir_not_exist(caplog):
    """Test pruning when the download directory does not exist."""
    caplog.set_level(logging.WARNING)
    non_existent_dir = "/path/to/some/non_existent_dir_for_prune"

    # Should not raise an error, just log a warning.
    prune_old_downloads(non_existent_dir, 3)

    assert (
        f"Download directory '{non_existent_dir}' not found. Skipping pruning."
        in caplog.text
    )


def test_prune_invalid_download_keep_value():
    """Test pruning with invalid (e.g., negative, non-integer) download_keep values."""
    with pytest.raises(
        UserInputError,
        match="Invalid value for downloads to keep: '-1'. Must be an integer >= 0.",
    ):
        prune_old_downloads("some_dir", -1)
    with pytest.raises(
        UserInputError,
        match="Invalid value for downloads to keep: 'abc'. Must be an integer >= 0.",
    ):
        prune_old_downloads("some_dir", "abc")  # type: ignore


def test_prune_missing_download_dir():
    """Test pruning when download_dir is None or empty."""
    with pytest.raises(
        MissingArgumentError, match="Download directory cannot be empty for pruning."
    ):
        prune_old_downloads(None, 3)  # type: ignore
    with pytest.raises(
        MissingArgumentError, match="Download directory cannot be empty for pruning."
    ):
        prune_old_downloads("", 3)


def test_prune_os_error_on_unlink(temp_download_base_dir: Path, mocker, caplog):
    """Test handling of OSError during file deletion (unlink)."""
    caplog.set_level(logging.INFO)  # Capture INFO for successful deletions too
    prune_dir = temp_download_base_dir / "prune_test_os_error"
    prune_dir.mkdir(parents=True, exist_ok=True)

    created_files = create_dummy_files_with_timestamps(prune_dir, 3)

    # Mock Path.unlink to raise OSError for the oldest file
    # The oldest file is created_files[0] due to mtime sorting in helper
    mocked_unlink = mocker.patch.object(Path, "unlink", autospec=True)

    def unlink_side_effect(path_instance):
        if path_instance == created_files[0]:
            # print(f"Mocking unlink failure for: {path_instance}")
            raise OSError("Test permission denied")
        # print(f"Mocking unlink success for: {path_instance}")
        # For other files, do nothing (simulate successful unlink by mock)
        # Actually, for non-mocked files, we need to call original or let it be.
        # If autospec=True, just raising for one and letting others pass through the mock (which does nothing) is fine.
        # However, if we want other files to actually be deleted, we need a more complex side_effect or multiple mocks.
        # For this test, we only care about the one failure and that others are attempted.
        pass

    # If we only want to mock the first one and let others proceed normally:
    # This is tricky with instance methods. A simpler way for this test might be to mock os.remove
    # if Path.unlink internally calls it, or ensure the mock only applies to the specific path.
    # The current `autospec=True` and side_effect raising only for one path means other calls to unlink on
    # other Path instances will go to their original method if not covered by this specific mock instance.
    # This is usually not how it works. The mock replaces Path.unlink for ALL instances.

    # Let's refine: only the first file to be deleted should fail.
    # `files_to_delete` in `prune_old_downloads` will be `created_files[:num_to_delete]`
    # If download_keep is 1, num_to_delete is 2. files_to_delete = [created_files[0], created_files[1]]

    files_that_should_be_deleted = [created_files[0], created_files[1]]
    file_to_fail_unlink = files_that_should_be_deleted[0]

    def selective_unlink_side_effect(
        path_instance_self,
    ):  # 'self' here is the Path instance
        if path_instance_self == file_to_fail_unlink:
            # print(f"Intentionally failing unlink for {path_instance_self}")
            raise OSError("Test permission denied on specific file")
        # For other files, we want them to be unlinked if they are supposed to be.
        # However, since we mocked Path.unlink, the original is gone.
        # This means we have to manually delete them or skip.
        # For this test, it's okay if the "successful" ones are just not raising errors.
        # print(f"Allowing unlink for {path_instance_self}")
        pass  # Mock simulates successful deletion by not raising error

    mocked_unlink.side_effect = selective_unlink_side_effect

    prune_old_downloads(str(prune_dir), 1)  # Keep 1, so 2 should be deleted

    # Check logs for the error
    assert (
        f"Failed to delete old server download '{file_to_fail_unlink}': Test permission denied on specific file"
        in caplog.text
    )

    # Check that the file that failed deletion still exists
    assert file_to_fail_unlink.exists()

    # Check that the other file meant for deletion (files_that_should_be_deleted[1]) was "processed" by mock (and thus appears deleted from prune's perspective)
    # and the one to keep (created_files[2]) still exists.
    if len(created_files) > 1:
        # The one that didn't fail unlink should appear gone to the function
        # but since our mock just 'passes', it might still be there.
        # This test primarily verifies error handling and logging for the FAILED one.
        # A more robust check would be to see how many times unlink was called.
        assert mocked_unlink.call_count == 2  # Called for the two files to be deleted.

    assert created_files[2].exists()  # The one to keep


# --- Tests for BedrockDownloader - Initialization ---


def test_downloader_initialization_success(
    mock_settings, temp_server_dir, temp_download_base_dir, mocker
):
    """Test successful initialization of BedrockDownloader."""

    # Ensure mock_settings returns the correct temp_download_base_dir for this test
    # This is similar to what downloader_instance fixture does.
    def settings_get_side_effect(key, default=None):
        if key == "paths.downloads":
            return str(temp_download_base_dir)
        return {  # Provide other necessary defaults if any
            "retention.downloads": 3,
            "_app_name": "TestBSM",
        }.get(key, default)

    mock_settings.get.side_effect = settings_get_side_effect
    # Mock platform.system as it's used in BedrockDownloader constructor and not by a fixture here
    mocker.patch("platform.system", return_value="Linux")

    downloader = BedrockDownloader(mock_settings, str(temp_server_dir), "1.20.10.01")
    assert downloader.settings == mock_settings
    assert downloader.server_dir == str(temp_server_dir)
    assert downloader.input_target_version == "1.20.10.01"
    assert (
        downloader.os_name == platform.system()
    )  # Or specific mocked value if platform is mocked globally
    assert downloader.base_download_dir == str(temp_download_base_dir)
    assert (
        downloader._version_type == "LATEST"
    )  # because "1.20.10.01" is treated as stable
    assert downloader._custom_version_number == "1.20.10.01"


def test_downloader_initialization_missing_args(mock_settings, temp_server_dir):
    """Test BedrockDownloader initialization with missing arguments."""
    with pytest.raises(MissingArgumentError, match="Settings object cannot be None"):
        BedrockDownloader(None, str(temp_server_dir), "LATEST")

    with pytest.raises(MissingArgumentError, match="Server directory cannot be empty"):
        BedrockDownloader(mock_settings, "", "LATEST")

    with pytest.raises(MissingArgumentError, match="Target version cannot be empty"):
        BedrockDownloader(mock_settings, str(temp_server_dir), "")


def test_downloader_initialization_missing_download_path_setting(
    mocker, temp_server_dir
):
    """Test BedrockDownloader if paths.downloads is missing in settings."""
    settings_no_download_path = mocker.MagicMock(spec=Settings)
    settings_no_download_path.get.side_effect = lambda key, default=None: {
        "retention.downloads": 3  # other settings might be fine
    }.get(
        key, default
    )  # paths.downloads will return None

    with pytest.raises(
        ConfigurationError, match="DOWNLOAD_DIR setting is missing or empty"
    ):
        BedrockDownloader(settings_no_download_path, str(temp_server_dir), "LATEST")


@pytest.mark.parametrize(
    "target_version_input, expected_version_type, expected_custom_number",
    [
        ("LATEST", "LATEST", ""),
        ("latest", "LATEST", ""),  # Test case-insensitivity for LATEST/PREVIEW
        ("PREVIEW", "PREVIEW", ""),
        ("preview", "PREVIEW", ""),
        ("1.20.10.01", "LATEST", "1.20.10.01"),
        ("1.19.80.20-PREVIEW", "PREVIEW", "1.19.80.20"),
        ("  1.20.30.02  ", "LATEST", "1.20.30.02"),  # Test stripping of whitespace
        ("  1.20.40.01-PREVIEW  ", "PREVIEW", "1.20.40.01"),
        ("CUSTOM", "CUSTOM", ""),
        ("custom", "CUSTOM", ""),
    ],
)
def test_downloader_determine_version_parameters(
    mock_settings,
    temp_server_dir,
    target_version_input,
    expected_version_type,
    expected_custom_number,
    tmp_path,
):
    """Test _determine_version_parameters with various version inputs."""
    if "custom" in target_version_input.lower():
        # Create a dummy file for the custom zip path to exist
        dummy_zip = tmp_path / "dummy.zip"
        dummy_zip.touch()
        downloader = BedrockDownloader(
            mock_settings,
            str(temp_server_dir),
            target_version_input,
            server_zip_path=str(dummy_zip),
        )
    else:
        downloader = BedrockDownloader(
            mock_settings, str(temp_server_dir), target_version_input
        )
    assert downloader._version_type == expected_version_type
    assert downloader._custom_version_number == expected_custom_number


# --- Tests for BedrockDownloader - URL Lookup ---


@pytest.fixture
def mock_requests_get(mocker):
    """Fixture to mock requests.get."""
    return mocker.patch("requests.get")


def common_api_response_data(
    download_type_linux,
    download_type_windows,
    version_linux="1.20.0.1",
    version_windows="1.20.0.2",
):
    return {
        "result": {
            "links": [
                {
                    "downloadType": download_type_linux,
                    "downloadUrl": f"https://minecraft.azureedge.net/bedrock-server-{version_linux}.zip",
                },
                {
                    "downloadType": download_type_windows,
                    "downloadUrl": f"https://minecraft.azureedge.net/bedrock-server-{version_windows}.zip",
                },
                # Add other types if needed for comprehensive testing, e.g., "serverBedrockAndroid"
            ]
        }
    }


@pytest.mark.parametrize(
    "os_name, target_version, expected_api_type, expected_version_from_url",
    [
        ("Linux", "LATEST", "serverBedrockLinux", "1.20.0.1"),
        ("Windows", "LATEST", "serverBedrockWindows", "1.20.0.2"),
        (
            "Linux",
            "PREVIEW",
            "serverBedrockPreviewLinux",
            "1.20.0.1",
        ),  # Assuming preview uses same mock URL version for simplicity
        ("Windows", "PREVIEW", "serverBedrockPreviewWindows", "1.20.0.2"),
    ],
)
def test_get_version_for_target_spec_latest_preview(
    downloader_instance,
    mock_requests_get,
    mocker,
    os_name,
    target_version,
    expected_api_type,
    expected_version_from_url,
):
    """Test get_version_for_target_spec for LATEST/PREVIEW on different OS."""
    mocker.patch("platform.system", return_value=os_name)
    downloader = BedrockDownloader(
        downloader_instance.settings, downloader_instance.server_dir, target_version
    )

    mock_response = mocker.Mock()
    api_data = common_api_response_data(
        "serverBedrockLinux",
        "serverBedrockWindows",
        version_linux="1.20.0.1",
        version_windows="1.20.0.2",
    )
    # Adjust if preview download types are different in the mock or need different versions
    if "Preview" in expected_api_type:
        api_data["result"]["links"].extend(
            [
                {
                    "downloadType": "serverBedrockPreviewLinux",
                    "downloadUrl": f"https://minecraft.azureedge.net/bedrock-server-preview-linux-{expected_version_from_url}.zip",
                },
                {
                    "downloadType": "serverBedrockPreviewWindows",
                    "downloadUrl": f"https://minecraft.azureedge.net/bedrock-server-preview-windows-{expected_version_from_url}.zip",
                },
            ]
        )
        # Ensure the correct preview URL is picked if the base one differs significantly in parsing
        # For this test, we'll assume the version extraction logic can handle "preview-os-version" format if it appears
        # The main goal is that it picks the right downloadType.
        # Let's simplify the mock to use a consistent version string for now
        for link in api_data["result"]["links"]:
            if link["downloadType"] == expected_api_type:
                link["downloadUrl"] = (
                    f"https://minecraft.azureedge.net/bedrock-server-{expected_version_from_url}.zip"
                )

    mock_response.json.return_value = api_data
    mock_response.raise_for_status = mocker.Mock()
    mock_requests_get.return_value = mock_response

    resolved_version = downloader.get_version_for_target_spec()

    mock_requests_get.assert_called_once()
    assert downloader.resolved_download_url.endswith(
        f"-{expected_version_from_url}.zip"
    )
    assert resolved_version == expected_version_from_url
    assert downloader.actual_version == expected_version_from_url


def test_get_version_for_target_spec_specific_version(
    downloader_instance, mock_requests_get, mocker
):
    """Test get_version_for_target_spec for a specific version string."""
    mocker.patch("platform.system", return_value="Linux")  # Assume Linux for this test
    target_version = "1.19.50.02"
    downloader = BedrockDownloader(
        downloader_instance.settings, downloader_instance.server_dir, target_version
    )

    mock_response = mocker.Mock()
    # API still returns its "latest" stable URL for the OS
    api_data = common_api_response_data(
        "serverBedrockLinux", "serverBedrockWindows", version_linux="1.20.0.1"
    )
    mock_response.json.return_value = api_data
    mock_response.raise_for_status = mocker.Mock()
    mock_requests_get.return_value = mock_response

    resolved_version = downloader.get_version_for_target_spec()

    mock_requests_get.assert_called_once()
    # The URL should be modified to the target_version
    assert downloader.resolved_download_url.endswith(f"-{target_version}.zip")
    # The actual_version should be the target_version
    assert resolved_version == target_version
    assert downloader.actual_version == target_version


def test_get_version_for_target_spec_specific_preview_version(
    downloader_instance, mock_requests_get, mocker
):
    """Test get_version_for_target_spec for a specific preview version string."""
    mocker.patch("platform.system", return_value="Windows")  # Assume Windows
    target_version = "1.19.80.20-PREVIEW"
    custom_number = "1.19.80.20"
    downloader = BedrockDownloader(
        downloader_instance.settings, downloader_instance.server_dir, target_version
    )

    mock_response = mocker.Mock()
    # API returns its "latest" PREVIEW URL for the OS
    api_data = common_api_response_data(
        "serverBedrockPreviewLinux",
        "serverBedrockPreviewWindows",
        version_windows="1.20.10.01",
    )  # Dummy latest preview version
    mock_response.json.return_value = api_data
    mock_response.raise_for_status = mocker.Mock()
    mock_requests_get.return_value = mock_response

    resolved_version = downloader.get_version_for_target_spec()

    mock_requests_get.assert_called_once()
    assert downloader.resolved_download_url.endswith(
        f"-{custom_number}.zip"
    )  # Preview tag is not in the final URL typically
    assert resolved_version == custom_number
    assert downloader.actual_version == custom_number


def test_lookup_unsupported_os(downloader_instance, mocker):
    """Test URL lookup on an unsupported OS."""
    mocker.patch("platform.system", return_value="Solaris")
    downloader = BedrockDownloader(
        downloader_instance.settings, downloader_instance.server_dir, "LATEST"
    )
    with pytest.raises(
        SystemError, match="Unsupported OS for Bedrock server download: Solaris"
    ):
        downloader.get_version_for_target_spec()


def test_lookup_requests_exception(downloader_instance, mock_requests_get):
    """Test URL lookup when requests.get raises an exception."""
    mock_requests_get.side_effect = requests.exceptions.RequestException(
        "Network Error"
    )
    with pytest.raises(
        InternetConnectivityError,
        match="Could not contact the Minecraft download API: Network Error",
    ):
        downloader_instance.get_version_for_target_spec()


def test_lookup_json_decode_error(downloader_instance, mock_requests_get, mocker):
    """Test URL lookup when API response is not valid JSON."""
    mock_response = mocker.Mock()
    mock_response.json.side_effect = json.JSONDecodeError("JSON error", "doc", 0)
    mock_response.raise_for_status = mocker.Mock()
    mock_requests_get.return_value = mock_response
    with pytest.raises(
        DownloadError, match="The Minecraft download API returned malformed data."
    ):
        downloader_instance.get_version_for_target_spec()


def test_lookup_api_missing_download_type(
    downloader_instance, mock_requests_get, mocker
):
    """Test URL lookup when API response is missing the required downloadType."""
    mocker.patch("platform.system", return_value="Linux")
    downloader = BedrockDownloader(
        downloader_instance.settings, downloader_instance.server_dir, "LATEST"
    )

    mock_response = mocker.Mock()
    api_data = {
        "result": {"links": [{"downloadType": "wrongType", "downloadUrl": "some_url"}]}
    }  # Missing serverBedrockLinux
    mock_response.json.return_value = api_data
    mock_response.raise_for_status = mocker.Mock()
    mock_requests_get.return_value = mock_response

    with pytest.raises(
        DownloadError,
        match="The API did not provide a download URL for your system \(serverBedrockLinux\).",
    ):
        downloader.get_version_for_target_spec()


def test_lookup_fail_to_construct_specific_url(
    downloader_instance, mock_requests_get, mocker
):
    """Test failure to construct URL for a specific version if base URL format changes."""
    mocker.patch("platform.system", return_value="Linux")
    downloader = BedrockDownloader(
        downloader_instance.settings, downloader_instance.server_dir, "1.19.50.02"
    )

    mock_response = mocker.Mock()
    # Provide a base URL that doesn't match the expected bedrock-server-VERSION.zip pattern
    api_data = {
        "result": {
            "links": [
                {
                    "downloadType": "serverBedrockLinux",
                    "downloadUrl": "https://example.com/some-other-format.zip",
                }
            ]
        }
    }
    mock_response.json.return_value = api_data
    mock_response.raise_for_status = mocker.Mock()
    mock_requests_get.return_value = mock_response

    with pytest.raises(
        DownloadError,
        match="Failed to construct URL for specific version '1.19.50.02'. The URL format may have changed.",
    ):
        downloader.get_version_for_target_spec()


def test_get_version_from_url_fail(downloader_instance):
    """Test _get_version_from_url when URL format is unexpected."""
    downloader_instance.resolved_download_url = "https://example.com/invalid-format.zip"
    with pytest.raises(
        DownloadError, match="Failed to extract version number from URL format"
    ):
        downloader_instance._get_version_from_url()  # Test protected member directly for this specific case


# --- Tests for BedrockDownloader - Downloading ---


@pytest.fixture
def mock_successful_requests_get_stream(mocker):
    """Mocks requests.get for a successful streaming download."""
    mock_response = mocker.Mock(spec=requests.Response)
    mock_response.raise_for_status = mocker.Mock()
    mock_response.status_code = 200  # Add status_code
    mock_response.headers = {"content-length": "100"}  # Dummy size
    mock_response.iter_content.return_value = [
        b"chunk1_data",
        b"chunk2_data",
    ]  # Dummy content
    mock_response.__enter__ = mocker.Mock(
        return_value=mock_response
    )  # For context manager
    mock_response.__exit__ = mocker.Mock(return_value=None)  # For context manager

    mock_get = mocker.patch("requests.get", return_value=mock_response)
    return mock_get, mock_response


def test_prepare_download_assets_success_new_download(
    downloader_instance, mock_successful_requests_get_stream, mocker
):
    """Test prepare_download_assets successfully downloads a new file."""
    mock_get, _ = mock_successful_requests_get_stream

    # Mock parts of the process leading up to download
    downloader_instance._lookup_bedrock_download_url = mocker.Mock(
        return_value="http://example.com/bedrock-server-1.20.0.zip"
    )
    downloader_instance._get_version_from_url = mocker.Mock(return_value="1.20.0")
    downloader_instance.actual_version = "1.20.0"  # Set by _get_version_from_url mock
    downloader_instance.resolved_download_url = "http://example.com/bedrock-server-1.20.0.zip"  # Set by _lookup_bedrock_download_url mock

    mocker.patch("bedrock_server_manager.core.system.base.check_internet_connectivity")
    mock_prune = mocker.patch(
        "bedrock_server_manager.core.downloader.prune_old_downloads"
    )

    actual_version, zip_file_path, specific_download_dir = (
        downloader_instance.prepare_download_assets()
    )

    assert actual_version == "1.20.0"
    expected_zip_path = (
        Path(downloader_instance.specific_download_dir) / "bedrock-server-1.20.0.zip"
    )
    assert zip_file_path == str(expected_zip_path)
    assert Path(zip_file_path).exists()
    with open(zip_file_path, "rb") as f:
        content = f.read()
        assert content == b"chunk1_datachunk2_data"

    mock_get.assert_called_once_with(
        "http://example.com/bedrock-server-1.20.0.zip",
        headers=mocker.ANY,
        stream=True,
        timeout=120,
    )
    mock_prune.assert_called_once()  # Ensure pruning was called
    assert Path(downloader_instance.specific_download_dir).exists()


def test_prepare_download_assets_file_already_exists(
    downloader_instance,
    mock_requests_get,
    mocker,  # Use general mock_requests_get as it shouldn't be called
):
    """Test prepare_download_assets skips download if file exists."""
    # Setup conditions as if version lookup was successful
    downloader_instance.actual_version = "1.19.0"
    downloader_instance.resolved_download_url = (
        "http://example.com/bedrock-server-1.19.0.zip"
    )
    downloader_instance._version_type = (
        "LATEST"  # For specific_download_dir calculation
    )

    # Determine where the file *would* be and create it
    # This relies on the internal logic of how specific_download_dir and zip_file_path are formed
    # which is okay for this test as we are testing the "already exists" branch.
    version_subdir_name = "stable"  # Based on _version_type = "LATEST"
    specific_dl_dir = Path(downloader_instance.base_download_dir) / version_subdir_name
    specific_dl_dir.mkdir(parents=True, exist_ok=True)
    downloader_instance.specific_download_dir = str(
        specific_dl_dir
    )  # Manually set for test

    expected_zip_path = specific_dl_dir / "bedrock-server-1.19.0.zip"
    expected_zip_path.write_text("existing dummy content")
    downloader_instance.zip_file_path = str(expected_zip_path)  # Manually set for test

    mocker.patch("bedrock_server_manager.core.system.base.check_internet_connectivity")
    mock_prune = mocker.patch(
        "bedrock_server_manager.core.downloader.prune_old_downloads"
    )

    # Mock the upstream calls that would normally set these, to ensure they are not the source of the file path
    downloader_instance._lookup_bedrock_download_url = mocker.Mock(
        return_value=downloader_instance.resolved_download_url
    )
    downloader_instance._get_version_from_url = mocker.Mock(
        return_value=downloader_instance.actual_version
    )

    actual_version, zip_file_path, specific_download_dir_out = (
        downloader_instance.prepare_download_assets()
    )

    assert actual_version == "1.19.0"
    assert zip_file_path == str(expected_zip_path)
    assert (
        Path(zip_file_path).read_text() == "existing dummy content"
    )  # Ensure it wasn't overwritten

    mock_requests_get.assert_not_called()  # Crucial: download should not occur
    mock_prune.assert_called_once()


def test_prepare_download_assets_internet_connectivity_error(
    downloader_instance, mocker
):
    """Test prepare_download_assets when internet check fails."""
    mocker.patch(
        "bedrock_server_manager.core.system.base.check_internet_connectivity",
        side_effect=InternetConnectivityError("No internet"),
    )

    with pytest.raises(InternetConnectivityError, match="No internet"):
        downloader_instance.prepare_download_assets()


def test_download_server_zip_file_request_exception(
    downloader_instance, mock_requests_get, mocker
):
    """Test _download_server_zip_file handles requests.get exception."""
    downloader_instance.resolved_download_url = "http://example.com/fail.zip"
    downloader_instance.specific_download_dir = str(
        Path(downloader_instance.settings.get("paths.downloads")) / "stable"
    )
    Path(downloader_instance.specific_download_dir).mkdir(parents=True, exist_ok=True)
    downloader_instance.zip_file_path = str(
        Path(downloader_instance.specific_download_dir) / "fail.zip"
    )

    mock_requests_get.side_effect = requests.exceptions.RequestException(
        "Download Network Error"
    )

    with pytest.raises(
        InternetConnectivityError,
        match="Download failed for 'http://example.com/fail.zip': Download Network Error",
    ):
        downloader_instance._download_server_zip_file()

    assert not Path(
        downloader_instance.zip_file_path
    ).exists()  # Check partial download cleanup


def test_download_server_zip_file_os_error_on_write(
    downloader_instance, mock_successful_requests_get_stream, mocker
):
    """Test _download_server_zip_file handles OSError during file write."""
    _, mock_response = (
        mock_successful_requests_get_stream  # We need mock_response for iter_content
    )

    downloader_instance.resolved_download_url = "http://example.com/write_fail.zip"
    downloader_instance.specific_download_dir = str(
        Path(downloader_instance.settings.get("paths.downloads")) / "stable"
    )
    Path(downloader_instance.specific_download_dir).mkdir(parents=True, exist_ok=True)
    downloader_instance.zip_file_path = str(
        Path(downloader_instance.specific_download_dir) / "write_fail.zip"
    )

    mocker.patch("builtins.open", side_effect=OSError("Cannot write to disk"))

    with pytest.raises(
        FileOperationError,
        match="Cannot write to file '.*/write_fail.zip': Cannot write to disk",
    ):
        downloader_instance._download_server_zip_file()


def test_prepare_download_assets_fail_create_dirs(downloader_instance, mocker):
    """Test prepare_download_assets when os.makedirs fails."""
    mocker.patch("bedrock_server_manager.core.system.base.check_internet_connectivity")
    mocker.patch("os.makedirs", side_effect=OSError("Permission denied to create dir"))

    # This mock needs to be specific enough not to break tmp_path_factory or other pytest mechanisms.
    # We are interested in the makedirs called by BedrockDownloader itself.
    # The first os.makedirs is for self.server_dir.

    with pytest.raises(
        FileOperationError,
        match="Failed to create required directories: Permission denied to create dir",
    ):
        downloader_instance.prepare_download_assets()


# --- Tests for BedrockDownloader - Extraction ---


def test_extract_server_files_fresh_install(
    downloader_instance, temp_server_dir, temp_download_base_dir
):
    """Test extract_server_files in fresh install mode."""
    zip_content = {
        "file1.txt": b"content1",
        "folder/file2.txt": b"content2",
        "worlds/myworld/level.dat": b"world_data",  # Should be extracted in fresh
        "server.properties": b"prop_fresh",
    }
    dummy_zip_path = temp_download_base_dir / "test_server.zip"
    create_dummy_zip(dummy_zip_path, zip_content)

    downloader_instance.zip_file_path = str(dummy_zip_path)
    # Ensure server_dir is empty for a true fresh install test
    for item in temp_server_dir.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    downloader_instance.extract_server_files(is_update=False)

    assert (temp_server_dir / "file1.txt").read_bytes() == b"content1"
    assert (temp_server_dir / "folder/file2.txt").read_bytes() == b"content2"
    assert (temp_server_dir / "worlds/myworld/level.dat").read_bytes() == b"world_data"
    assert (temp_server_dir / "server.properties").read_bytes() == b"prop_fresh"


def test_extract_server_files_update_mode(
    downloader_instance, temp_server_dir, temp_download_base_dir
):
    """Test extract_server_files in update mode, preserving specified items."""
    # Existing files in server_dir that should be preserved
    preserved_world_path = temp_server_dir / "worlds" / "existing_world"
    preserved_world_path.mkdir(parents=True, exist_ok=True)
    (preserved_world_path / "level.dat").write_bytes(b"preserved_world_data")

    preserved_properties_path = temp_server_dir / "server.properties"
    preserved_properties_path.write_bytes(b"preserved_properties")

    preserved_allowlist_path = temp_server_dir / "allowlist.json"
    preserved_allowlist_path.write_bytes(b"preserved_allowlist")

    # Other existing file that should be overwritten
    other_existing_file = temp_server_dir / "other_file.txt"
    other_existing_file.write_bytes(b"old_other_data")

    # Content of the new ZIP file
    zip_content = {
        "new_file.txt": b"new_zip_content",
        "worlds/new_world_in_zip/level.dat": b"zip_world_data",  # Should not overwrite existing worlds dir
        "server.properties": b"zip_properties",  # Should not overwrite
        "allowlist.json": b"zip_allowlist",  # Should not overwrite
        "permissions.json": b"zip_permissions",  # Should be extracted as it's in PRESERVED_ITEMS_ON_UPDATE
        "other_file.txt": b"new_zip_other_data",  # Should overwrite
    }
    dummy_zip_path = temp_download_base_dir / "update_server.zip"
    create_dummy_zip(dummy_zip_path, zip_content)
    downloader_instance.zip_file_path = str(dummy_zip_path)

    downloader_instance.extract_server_files(is_update=True)

    # Check preserved files
    assert (preserved_world_path / "level.dat").read_bytes() == b"preserved_world_data"
    assert preserved_properties_path.read_bytes() == b"preserved_properties"
    assert preserved_allowlist_path.read_bytes() == b"preserved_allowlist"

    # Check new files are extracted
    assert (temp_server_dir / "new_file.txt").read_bytes() == b"new_zip_content"
    # The PRESERVED_ITEMS_ON_UPDATE is for top-level items.
    # If "worlds/" is preserved, new worlds from zip shouldn't be added *unless* the logic is more granular.
    # The current code: `member_path == item or member_path.startswith(item)`
    # So "worlds/new_world_in_zip/level.dat" will be skipped because it starts with "worlds/".
    assert not (temp_server_dir / "worlds/new_world_in_zip").exists()

    # Check items listed in PRESERVED_ITEMS_ON_UPDATE:
    # If it was in the zip (like permissions.json), it should NOT be extracted if it's on the preserve list.
    # The PRESERVED_ITEMS_ON_UPDATE means these items in the server_dir are protected from being overwritten by the zip.
    # If permissions.json was NOT in server_dir before, and it's in PRESERVED_ITEMS_ON_UPDATE, it will NOT be extracted from zip.
    assert not (
        temp_server_dir / "permissions.json"
    ).exists()  # It wasn't there before, and it's preserved, so not extracted.

    # Check overwritten files (those not in PRESERVED_ITEMS_ON_UPDATE)
    assert (temp_server_dir / "other_file.txt").read_bytes() == b"new_zip_other_data"


def test_extract_bad_zip_file(
    downloader_instance, temp_server_dir, temp_download_base_dir
):
    """Test extract_server_files with a corrupted ZIP file."""
    bad_zip_path = temp_download_base_dir / "bad.zip"
    bad_zip_path.write_bytes(b"this is not a zip file")
    downloader_instance.zip_file_path = str(bad_zip_path)

    with pytest.raises(ExtractError, match="Invalid ZIP file"):
        downloader_instance.extract_server_files(is_update=False)


def test_extract_os_error(downloader_instance, temp_download_base_dir, mocker):
    """Test extract_server_files when an OSError occurs during extraction."""
    dummy_zip_path = temp_download_base_dir / "os_error_test.zip"
    create_dummy_zip(dummy_zip_path, {"file.txt": b"data"})
    downloader_instance.zip_file_path = str(dummy_zip_path)

    mocker.patch("zipfile.ZipFile.extractall", side_effect=OSError("Disk full"))

    with pytest.raises(
        FileOperationError, match="Error during file extraction: Disk full"
    ):
        downloader_instance.extract_server_files(is_update=False)


def test_extract_missing_zip_file_path(downloader_instance):
    """Test extract_server_files if zip_file_path is not set."""
    downloader_instance.zip_file_path = None
    with pytest.raises(MissingArgumentError, match="ZIP file path not set."):
        downloader_instance.extract_server_files(is_update=False)


def test_extract_zip_file_does_not_exist(downloader_instance, temp_download_base_dir):
    """Test extract_server_files if the zip file itself does not exist."""
    downloader_instance.zip_file_path = str(temp_download_base_dir / "non_existent.zip")
    with pytest.raises(AppFileNotFoundError, match="non_existent.zip"):
        downloader_instance.extract_server_files(is_update=False)


# --- Tests for BedrockDownloader - Full Setup ---


def test_full_server_setup_success(downloader_instance, mocker):
    """Test full_server_setup successfully orchestrates download and extraction."""
    expected_version = "1.21.0"
    expected_zip_path = "/fake/downloads/stable/bedrock-server-1.21.0.zip"
    expected_specific_dir = "/fake/downloads/stable"

    mock_prepare = mocker.patch.object(
        downloader_instance,
        "prepare_download_assets",
        return_value=(expected_version, expected_zip_path, expected_specific_dir),
    )
    mock_extract = mocker.patch.object(downloader_instance, "extract_server_files")

    returned_version = downloader_instance.full_server_setup(is_update=True)

    assert returned_version == expected_version
    mock_prepare.assert_called_once_with()  # prepare_download_assets takes no args itself
    mock_extract.assert_called_once_with(True)  # Positional argument


def test_full_server_setup_prepare_fails(downloader_instance, mocker):
    """Test full_server_setup when prepare_download_assets fails."""
    mock_prepare = mocker.patch.object(
        downloader_instance,
        "prepare_download_assets",
        side_effect=DownloadError("Failed to prepare assets"),
    )
    mock_extract = mocker.patch.object(downloader_instance, "extract_server_files")

    with pytest.raises(DownloadError, match="Failed to prepare assets"):
        downloader_instance.full_server_setup(is_update=False)

    mock_prepare.assert_called_once_with()
    mock_extract.assert_not_called()  # Extraction should not be called if prepare fails


def test_full_server_setup_extract_fails(downloader_instance, mocker):
    """Test full_server_setup when extract_server_files fails."""
    expected_version = "1.21.0"
    mock_prepare = mocker.patch.object(
        downloader_instance,
        "prepare_download_assets",
        return_value=(expected_version, "dummy.zip", "dummy_dir"),
    )
    mock_extract = mocker.patch.object(
        downloader_instance,
        "extract_server_files",
        side_effect=ExtractError("Failed to extract"),
    )

    with pytest.raises(ExtractError, match="Failed to extract"):
        downloader_instance.full_server_setup(is_update=True)

    mock_prepare.assert_called_once_with()
    mock_extract.assert_called_once_with(True)  # Positional argument


# --- Tests for BedrockDownloader - Getter Methods ---


def test_downloader_getters_initial_state(mock_settings, temp_server_dir):
    """Test getter methods return None or initial values before operations."""
    # Create a downloader instance without calling any processing methods yet
    downloader = BedrockDownloader(mock_settings, str(temp_server_dir), "LATEST")

    assert downloader.get_actual_version() is None
    assert downloader.get_zip_file_path() is None
    assert downloader.get_specific_download_dir() is None
    assert downloader.get_resolved_download_url() is None


def test_downloader_getters_after_version_lookup(
    downloader_instance, mock_requests_get, mocker
):
    """Test getters after get_version_for_target_spec populates some attributes."""
    mocker.patch("platform.system", return_value="Linux")
    target_version = "1.18.0"
    downloader = BedrockDownloader(
        downloader_instance.settings, downloader_instance.server_dir, target_version
    )

    mock_response = mocker.Mock()
    api_data = common_api_response_data(
        "serverBedrockLinux", "serverBedrockWindows", version_linux="1.20.0.1"
    )
    mock_response.json.return_value = api_data
    mock_response.raise_for_status = mocker.Mock()
    mock_requests_get.return_value = mock_response

    resolved_version = (
        downloader.get_version_for_target_spec()
    )  # This populates some attributes

    assert downloader.get_actual_version() == target_version
    assert downloader.get_resolved_download_url() is not None
    assert downloader.get_resolved_download_url().endswith(f"-{target_version}.zip")

    # These are populated by prepare_download_assets, not just version lookup
    assert downloader.get_zip_file_path() is None
    assert downloader.get_specific_download_dir() is None


def test_downloader_getters_after_prepare_assets(
    downloader_instance, mock_successful_requests_get_stream, mocker
):
    """Test getters after prepare_download_assets populates all relevant attributes."""
    mock_get, _ = mock_successful_requests_get_stream

    # Mock parts of the process leading up to download
    downloader_instance._lookup_bedrock_download_url = mocker.Mock(
        return_value="http://example.com/bedrock-server-1.20.0.zip"
    )
    downloader_instance._get_version_from_url = mocker.Mock(return_value="1.20.0")
    # Manually set these as they would be by the mocked methods above
    downloader_instance.actual_version = "1.20.0"
    downloader_instance.resolved_download_url = (
        "http://example.com/bedrock-server-1.20.0.zip"
    )

    mocker.patch("bedrock_server_manager.core.system.base.check_internet_connectivity")
    mocker.patch("bedrock_server_manager.core.downloader.prune_old_downloads")

    downloader_instance.prepare_download_assets()

    assert downloader_instance.get_actual_version() == "1.20.0"
    assert (
        downloader_instance.get_resolved_download_url()
        == "http://example.com/bedrock-server-1.20.0.zip"
    )

    expected_specific_dir = Path(downloader_instance.base_download_dir) / (
        "stable" if downloader_instance._version_type == "LATEST" else "preview"
    )
    assert downloader_instance.get_specific_download_dir() == str(expected_specific_dir)

    expected_zip_path = expected_specific_dir / "bedrock-server-1.20.0.zip"
    assert downloader_instance.get_zip_file_path() == str(expected_zip_path)


def test_prepare_download_assets_custom_zip_success(
    downloader_instance, mock_requests_get, mocker, temp_download_base_dir
):
    """Test prepare_download_assets with a custom local ZIP file."""
    # This test should not call the network
    mocker.patch("bedrock_server_manager.core.downloader.prune_old_downloads")

    # 1. Create a dummy custom zip file
    custom_zip_dir = temp_download_base_dir / "custom"
    custom_zip_dir.mkdir(exist_ok=True)
    custom_zip_path = custom_zip_dir / "my-custom-server-1.0.0.zip"
    create_dummy_zip(custom_zip_path, {"custom_file.txt": b"custom data"})

    # 2. Re-initialize downloader for a CUSTOM target
    downloader = BedrockDownloader(
        downloader_instance.settings,
        downloader_instance.server_dir,
        "CUSTOM",
        server_zip_path=str(custom_zip_path),
    )

    # 3. Run the prepare assets function
    actual_version, zip_file_path, specific_download_dir = (
        downloader.prepare_download_assets()
    )

    # 4. Assertions
    assert actual_version == "1.0.0"  # Version should be extracted from filename
    assert zip_file_path == str(custom_zip_path)
    # For custom zips, specific_download_dir is the 'custom' folder
    assert Path(specific_download_dir).name == "custom"
    assert Path(zip_file_path).exists()

    # Crucially, ensure no network activity occurred
    mock_requests_get.assert_not_called()


def test_prepare_download_assets_custom_zip_not_found(downloader_instance):
    """Test prepare_download_assets with a non-existent custom ZIP file."""
    non_existent_zip_path = "/path/to/non_existent.zip"

    with pytest.raises(
        AppFileNotFoundError,
        match=f"Custom server ZIP file not found",
    ):
        BedrockDownloader(
            downloader_instance.settings,
            downloader_instance.server_dir,
            "CUSTOM",
            server_zip_path=non_existent_zip_path,
        )
