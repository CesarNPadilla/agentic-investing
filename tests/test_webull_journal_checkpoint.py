import json
import sqlite3
from uuid import uuid4

import pytest

from security.webull_journal_checkpoint import create_frozen_checkpoint, verify_frozen_checkpoint
from security.webull_request_journal import RequestJournal


def setup(tmp_path):
    (tmp_path / "state").mkdir()
    (tmp_path / "receipts").mkdir()
    journal = RequestJournal.initialize(
        tmp_path / "state" / "journal.sqlite", "a" * 64, state_digest="b" * 64
    )
    journal.register(
        json.dumps(
            {
                "schema_version": "webull-control-request-v1",
                "action": "REQUEST_RESET_REVIEW",
                "account_binding_sha256": "a" * 64,
                "expected_state_sha256": "b" * 64,
                "request_id": str(uuid4()),
            }
        ).encode()
    )
    return journal, tmp_path / "receipts" / "checkpoint.json"


def test_checkpoint_survives_restart_without_recovery_authority(tmp_path):
    journal, path = setup(tmp_path)
    create_frozen_checkpoint(journal, path)
    receipt = verify_frozen_checkpoint(RequestJournal(journal.path, journal.binding), path)
    assert receipt == {
        "frozen_snapshot_matches": True,
        "retained_requests": 1,
        "recovery_authorized": False,
        "execution_available": False,
    }
    with pytest.raises(FileExistsError):
        create_frozen_checkpoint(journal, path)


def test_deleted_history_fails_against_retained_checkpoint(tmp_path):
    journal, path = setup(tmp_path)
    create_frozen_checkpoint(journal, path)
    with sqlite3.connect(journal.path) as db:
        db.execute("DELETE FROM requests")
    # Internal digest verification alone cannot detect deletion.
    assert journal.verify()["retained_requests"] == 0
    with pytest.raises(ValueError, match="mismatch"):
        verify_frozen_checkpoint(journal, path)


def test_context_rollback_fails_against_checkpoint(tmp_path):
    journal, path = setup(tmp_path)
    create_frozen_checkpoint(journal, path)
    with sqlite3.connect(journal.path) as db:
        db.execute("UPDATE context SET state_digest=?", ("c" * 64,))
    with pytest.raises(ValueError, match="mismatch"):
        verify_frozen_checkpoint(journal, path)


def test_missing_checkpoint_and_same_directory_are_rejected(tmp_path):
    journal, path = setup(tmp_path)
    with pytest.raises(FileNotFoundError):
        verify_frozen_checkpoint(journal, path)
    with pytest.raises(ValueError, match="separate"):
        create_frozen_checkpoint(journal, journal.path.with_suffix(".json"))


def test_checkpoint_cannot_claim_recovery_authority(tmp_path):
    journal, path = setup(tmp_path)
    record = create_frozen_checkpoint(journal, path)
    record["recovery_authorized"] = True
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="mismatch"):
        verify_frozen_checkpoint(journal, path)
