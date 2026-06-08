import pytest

from bedrock_server_manager.error import AppFileNotFoundError, FileOperationError
from bedrock_server_manager.utils import list_content_files


def test_list_content_files_success(tmp_path):
    """Test _list_content_files successfully lists files."""
    worlds_dir = tmp_path / "worlds"
    worlds_dir.mkdir()
    (worlds_dir / "world1.mcworld").touch()
    (worlds_dir / "world2.mcworld").touch()
    (worlds_dir / "other.txt").touch()

    result = list_content_files(str(tmp_path), "worlds", [".mcworld"])
    assert len(result) == 2
    assert any("world1.mcworld" in f for f in result)
    assert any("world2.mcworld" in f for f in result)
    assert not any("other.txt" in f for f in result)


def test_list_content_files_no_matches(tmp_path):
    """Test _list_content_files when no files match extensions."""
    addons_dir = tmp_path / "addons"
    addons_dir.mkdir()
    (addons_dir / "something.txt").touch()

    result = list_content_files(str(tmp_path), "addons", [".mcpack", ".mcaddon"])
    assert result == []


def test_list_content_files_subfolder_not_exist(tmp_path):
    """Test _list_content_files when the sub_folder does not exist."""
    result = list_content_files(str(tmp_path), "non_existent_subfolder", [".txt"])
    assert result == []


def test_list_content_files_main_content_dir_not_exist():
    """Test _list_content_files raises AppFileNotFoundError if main content_dir is invalid."""
    with pytest.raises(AppFileNotFoundError, match="Content directory"):
        list_content_files(
            "/path/that/definitely/does/not/exist/12345", "worlds", [".mcworld"]
        )


def test_list_content_files_os_error_on_glob(tmp_path, mocker):
    """Test _list_content_files handles OSError from find_files."""
    worlds_dir = tmp_path / "worlds"
    worlds_dir.mkdir()

    mocker.patch(
        "bedrock_server_manager.api.application.find_files",
        side_effect=OSError("Glob permission denied"),
    )

    with pytest.raises(FileOperationError, match="Error scanning content directory"):
        list_content_files(str(tmp_path), "worlds", [".mcworld"])
