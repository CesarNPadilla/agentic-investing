import sqlite3

import pytest

from portfolio.webull_activity_store import WebullActivityStore


def evidence():
    return {
        "schema_version": "webull-cash-page-acquisition-v1",
        "records": [],
        "external_flow_total": None,
        "execution_available": False,
        "trial_started": False,
        "blockers": [
            "ACTIVITY_PUBLICATION_UNQUALIFIED",
            "ACTIVITY_EFFECTIVE_TIME_UNQUALIFIED",
            "ACCOUNT_ASOF_UNQUALIFIED",
        ],
    }


def test_independent_empty_observations_are_retained_after_restart(tmp_path):
    path = tmp_path / "observations.sqlite"
    store = WebullActivityStore.initialize(path, "a" * 64)
    store.append(evidence())
    store.append(evidence())
    report = WebullActivityStore(path, "a" * 64).verify()
    assert report["retained_observations"] == 2
    assert report["external_flow_total"] is None and not report["authoritative_ledger"]


def test_existing_database_and_observation_id_are_not_overwritten(tmp_path):
    path = tmp_path / "observations.sqlite"
    store = WebullActivityStore.initialize(path, "a" * 64)
    with pytest.raises(FileExistsError):
        WebullActivityStore.initialize(path, "a" * 64)
    store.append(evidence(), observation_id="one")
    with pytest.raises(sqlite3.IntegrityError):
        store.append(evidence(), observation_id="one")
    assert store.verify()["retained_observations"] == 1


@pytest.mark.parametrize(
    "change", [{"execution_available": True}, {"external_flow_total": "0"}, {"blockers": []}]
)
def test_no_qualification_or_execution_promotion(tmp_path, change):
    store = WebullActivityStore.initialize(tmp_path / "state.sqlite", "a" * 64)
    with pytest.raises(ValueError):
        store.append(evidence() | change)
    assert store.verify()["retained_observations"] == 0


def test_account_binding_and_corrupt_payload_block_append(tmp_path):
    path = tmp_path / "state.sqlite"
    store = WebullActivityStore.initialize(path, "a" * 64)
    store.append(evidence())
    with pytest.raises(ValueError):
        WebullActivityStore(path, "b" * 64).verify()
    with sqlite3.connect(path) as db:
        db.execute("UPDATE observations SET payload='changed'")
    with pytest.raises(ValueError):
        store.append(evidence())
