from concurrent.futures import ThreadPoolExecutor

from bedrock_server_manager.state_version import StateClock


def test_revisions_are_unique_across_threads_and_epochs_change_per_instance():
    clock = StateClock()
    with ThreadPoolExecutor(max_workers=8) as executor:
        versions = list(executor.map(lambda _: clock.capture(), range(1000)))
    assert sorted(version["revision"] for version in versions) == list(range(1, 1001))
    assert {version["epoch"] for version in versions} == {clock.epoch}
    assert StateClock().epoch != clock.epoch
