import pytest
import time
import asyncio
from unittest.mock import MagicMock, AsyncMock
from bedrock_server_manager.web.tasks import TaskManager
from bedrock_server_manager.error import BSMError


@pytest.fixture
def task_manager(mocker):
    """Fixture to create a new TaskManager for each test, with a mocked AppContext."""
    # Mock the AppContext and its dependencies needed by TaskManager
    mock_app_context = MagicMock()
    # The methods on connection_manager are async, so we need an AsyncMock
    mock_app_context.connection_manager = AsyncMock()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    mock_app_context.loop = loop

    tm = TaskManager(app_context=mock_app_context)
    yield tm
    tm.shutdown()


def test_run_task_success(task_manager):
    """Test running a task that completes successfully."""
    target_function = MagicMock(return_value={"status": "success"})

    task_id = task_manager.run_task(
        target_function, "testuser", "arg1", kwarg1="kwarg1"
    )

    # Wait for the task to complete by shutting down the executor
    task_manager.executor.shutdown(wait=True)

    status = task_manager.get_task(task_id)
    assert status["status"] == "success"
    assert status["result"] == {"status": "success"}
    target_function.assert_called_once_with("arg1", kwarg1="kwarg1")
    # Check that the notification was sent
    task_manager.app_context.connection_manager.send_to_user.assert_called()


def test_run_task_failure(task_manager):
    """Test running a task that fails."""
    target_function = MagicMock(side_effect=BSMError("Task failed"))

    task_id = task_manager.run_task(target_function, "testuser")

    # Wait for the task to complete
    task_manager.executor.shutdown(wait=True)

    status = task_manager.get_task(task_id)
    assert status["status"] == "error"
    assert "Task failed" in status["message"]
    task_manager.app_context.connection_manager.send_to_user.assert_called()


def test_get_task_not_found(task_manager):
    """Test getting the status of a task that does not exist."""
    status = task_manager.get_task("invalid_task_id")
    assert status is None


def test_task_status_progression(task_manager):
    """Test that a task is in 'in_progress' state before it completes."""

    # A function that takes a moment to run
    def long_running_task():
        time.sleep(0.1)
        return "done"

    task_id = task_manager.run_task(long_running_task, "testuser")

    # Check status immediately after starting
    status = task_manager.get_task(task_id)
    assert status["status"] == "in_progress"

    # Wait for completion
    task_manager.executor.shutdown(wait=True)

    # Check final status
    status = task_manager.get_task(task_id)
    assert status["status"] == "success"
    assert status["result"] == "done"


def test_run_task_after_shutdown_fails(task_manager):
    """Test that running a task after shutdown fails."""
    target_function = MagicMock()
    task_manager.shutdown()

    with pytest.raises(
        RuntimeError, match="Cannot start new tasks after shutdown has been initiated."
    ):
        task_manager.run_task(target_function)
