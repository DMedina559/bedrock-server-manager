from concurrent.futures import ThreadPoolExecutor

from bedrock_server_manager.state_revision import RevisionClock


def test_revisions_are_unique_across_threads_and_epochs_change_per_instance():
    clock = RevisionClock()
    with ThreadPoolExecutor(max_workers=8) as executor:
        revisions = list(executor.map(lambda _: clock.capture(), range(1000)))
    assert sorted(revision["revision"] for revision in revisions) == list(
        range(1, 1001)
    )
    assert {revision["epoch"] for revision in revisions} == {clock.epoch}
    assert RevisionClock().epoch != clock.epoch


def test_state_revision_requires_complete_valid_metadata():
    import pytest
    from pydantic import ValidationError

    from bedrock_server_manager.api.models.common import StateRevision

    assert StateRevision().epoch is None
    assert StateRevision(epoch="instance", revision=1).revision == 1
    for data in (
        {"epoch": "instance"},
        {"revision": 1},
        {"epoch": " ", "revision": 1},
        {"epoch": "instance", "revision": 2**53},
    ):
        with pytest.raises(ValidationError):
            StateRevision(**data)
