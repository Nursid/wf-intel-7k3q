import pytest

from app.services.data_repository import DataRepository
from app.services.elexon_client import ElexonUnavailableError
from tests.conftest import FakeClient


def test_fetches_then_serves_from_memory_and_disk(settings):
    fake = FakeClient()
    repo = DataRepository(settings, client_factory=lambda: fake)
    ds = repo.get()
    assert repo.status.cache_status == "network" and fake.calls == 1
    assert ds.meta.source == "elexon-live"
    assert ds.meta.normalization["actuals"]["non_wind"] == 95  # synthetic CCGT rows filtered out
    repo.get()
    assert repo.status.cache_status == "memory" and fake.calls == 1

    # a new process reads the disk cache without touching the network
    fake2 = FakeClient()
    repo2 = DataRepository(settings, client_factory=lambda: fake2)
    ds2 = repo2.get()
    assert repo2.status.cache_status == "disk" and fake2.calls == 0
    assert len(ds2.forecasts) == len(ds.forecasts)
    assert ds2.forecasts["publish_time_utc"].equals(ds.forecasts["publish_time_utc"])


def test_source_failure_without_cache_raises(settings):
    repo = DataRepository(settings, client_factory=lambda: FakeClient(fail=ElexonUnavailableError("down")))
    with pytest.raises(ElexonUnavailableError):
        repo.get()
    assert repo.status.last_error == "down"


def test_source_failure_with_expired_cache_serves_stale(settings):
    DataRepository(settings, client_factory=FakeClient).get()
    expired = settings.model_copy(update={"cache_ttl_hours": 1e-9})
    repo = DataRepository(expired, client_factory=lambda: FakeClient(fail=ElexonUnavailableError("down")))
    ds = repo.get()
    assert repo.status.cache_status == "stale-disk"
    assert repo.status.last_error == "down"
    assert not ds.actuals.empty


def test_empty_source_is_an_error(settings):
    repo = DataRepository(settings, client_factory=lambda: FakeClient(raw=([], [])))
    with pytest.raises(ElexonUnavailableError, match="no usable data"):
        repo.get()


def test_fixture_mode_is_labelled(settings):
    repo = DataRepository(settings.model_copy(update={"data_mode": "fixture"}))
    ds = repo.get()
    assert ds.meta.source == "fixture"
    assert repo.status.cache_status == "fixture"
    assert not ds.forecasts.empty
