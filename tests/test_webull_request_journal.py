import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from security.webull_request_journal import RequestJournal


def request(*, identifier=None, state="b" * 64):
    return json.dumps(
        {
            "schema_version": "webull-control-request-v1",
            "action": "REQUEST_RESET_REVIEW",
            "account_binding_sha256": "a" * 64,
            "expected_state_sha256": state,
            "request_id": identifier or str(uuid4()),
        }
    ).encode()


def create(tmp_path):
    return RequestJournal.initialize(tmp_path / "journal.sqlite", "a" * 64, state_digest="b" * 64)


def test_restart_preserves_request_consumption_without_authority(tmp_path):
    journal = create(tmp_path)
    raw = request()
    receipt = journal.register(raw)
    assert receipt["request_replay_checked"] and receipt["expected_state_matches"]
    assert not receipt["state_digest_verified"] and not receipt["controller_admitted"]
    assert not receipt["owner_approval_verified"] and not receipt["reset_performed"]
    reopened = RequestJournal(journal.path, "a" * 64)
    with pytest.raises(ValueError, match="replay"):
        reopened.register(raw)
    assert reopened.verify()["retained_requests"] == 1


def test_stale_state_is_recorded_blocked_and_cannot_be_replayed(tmp_path):
    journal = create(tmp_path)
    raw = request(state="c" * 64)
    receipt = journal.register(raw)
    assert not receipt["expected_state_matches"]
    assert "EXPECTED_STATE_CHANGED" in receipt["blockers"]
    with pytest.raises(ValueError, match="replay"):
        journal.register(raw)


def test_concurrent_duplicate_has_one_registration(tmp_path):
    journal = create(tmp_path)
    raw = request()

    def submit(_):
        try:
            return journal.register(raw)["request_registered"]
        except ValueError as error:
            assert "replay" in str(error)
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(submit, range(2))) == [False, True]
    assert journal.verify()["retained_requests"] == 1


def test_account_change_and_corrupted_receipt_block_further_writes(tmp_path):
    journal = create(tmp_path)
    journal.register(request())
    with pytest.raises(ValueError, match="binding"):
        RequestJournal(journal.path, "c" * 64).verify()
    with sqlite3.connect(journal.path) as db, db:
        db.execute("UPDATE requests SET receipt='{}'")
    with pytest.raises(ValueError, match="invalid"):
        journal.register(request())
    with sqlite3.connect(journal.path) as db:
        assert db.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 1


def test_existing_file_and_missing_journal_are_never_adopted(tmp_path):
    journal = create(tmp_path)
    with pytest.raises(FileExistsError):
        RequestJournal.initialize(journal.path, "a" * 64, state_digest="b" * 64)
    with pytest.raises(sqlite3.OperationalError):
        RequestJournal(tmp_path / "missing.sqlite", "a" * 64).register(request())
    assert not (tmp_path / "missing.sqlite").exists()


def test_invalid_request_does_not_consume_journal_entry(tmp_path):
    journal = create(tmp_path)
    with pytest.raises(ValueError):
        journal.register(b'{"action":"CLEAR_LATCH"}')
    assert journal.verify()["retained_requests"] == 0
