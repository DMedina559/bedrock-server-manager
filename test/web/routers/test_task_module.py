import pytest
import time
from unittest.mock import MagicMock
from bedrock_server_manager.web.tasks import TaskManager
from bedrock_server_manager.error import BSMError


@pytest.fixture
def task_manager():
    """Fixture to create a new TaskManager for each test."""
    tm = TaskManager()
    yield tm
    tm.shutdown()


def test_run_task_success(task_manager):
    """Test running a task that completes successfully."""
    target_function = MagicMock(return_value={"status": "success"})

    task_id = task_manager.run_task(target_function, "arg1", kwarg1="kwarg1")

    # Wait for the task to complete by shutting down the executor
    task_manager.executor.shutdown(wait=True)

    status = task_manager.get_task(task_id)
    assert status["status"] == "success"
    assert status["result"] == {"status": "success"}
    target_function.assert_called_once_with("arg1", kwarg1="kwarg1")


def test_run_task_failure(task_manager):
    """Test running a task that fails."""
    target_function = MagicMock(side_effect=BSMError("Task failed"))

    task_id = task_manager.run_task(target_function)

    # Wait for the task to complete
    task_manager.executor.shutdown(wait=True)

    status = task_manager.get_task(task_id)
    assert status["status"] == "error"
    assert "Task failed" in status["message"]


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

    task_id = task_manager.run_task(long_running_task)

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
