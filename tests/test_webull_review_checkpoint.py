import json
import sqlite3

import pytest

from security.webull_review_checkpoint import create_review_checkpoint, verify_review_checkpoint
from security.webull_review_journal import ReviewJournal
from tests.test_webull_review_signature import signed_review


def setup(tmp_path, *, consume=True):
    receipt, credential, envelope, now, _ = signed_review()
    (tmp_path / "state").mkdir()
    (tmp_path / "anchor").mkdir()
    journal = ReviewJournal.initialize(tmp_path / "state/review.sqlite", expected_envelope=envelope)
    if consume:
        journal.consume(receipt, credential, now=now)
    return journal, credential, tmp_path / "anchor/checkpoint.json"


def test_signed_consumption_checkpoint_survives_restart_and_never_authorizes(tmp_path):
    journal, credential, path = setup(tmp_path)
    create_review_checkpoint(journal, credential, path)
    restarted = ReviewJournal(journal.path, expected_envelope=journal.expected_envelope)
    assert verify_review_checkpoint(restarted, credential, path) == {
        "frozen_review_matches": True,
        "recovery_authorized": False,
        "reset_authorized": False,
        "execution_available": False,
    }
    with pytest.raises(FileExistsError):
        create_review_checkpoint(journal, credential, path)


def test_deleted_consumption_is_detected_against_retained_reference(tmp_path):
    journal, credential, path = setup(tmp_path)
    create_review_checkpoint(journal, credential, path)
    with sqlite3.connect(journal.path) as db:
        db.execute("DELETE FROM reviews")
    assert journal.verify(credential)["retained_review_count"] == 0
    with pytest.raises(ValueError):
        verify_review_checkpoint(journal, credential, path)


def test_unconsumed_context_cannot_create_consumption_checkpoint(tmp_path):
    journal, credential, path = setup(tmp_path, consume=False)
    with pytest.raises(ValueError):
        create_review_checkpoint(journal, credential, path)
    assert not path.exists()


@pytest.mark.parametrize("failure", ["missing", "same_directory", "authority", "digest"])
def test_incomplete_or_altered_reference_blocks_recovery(tmp_path, failure):
    journal, credential, path = setup(tmp_path)
    if failure == "missing":
        with pytest.raises(FileNotFoundError):
            verify_review_checkpoint(journal, credential, path)
        return
    if failure == "same_directory":
        with pytest.raises(ValueError):
            create_review_checkpoint(journal, credential, journal.path.with_suffix(".json"))
        return
    record = create_review_checkpoint(journal, credential, path)
    record["reset_authorized" if failure == "authority" else "consumed_snapshot_sha256"] = (
        True if failure == "authority" else "c" * 64
    )
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        verify_review_checkpoint(journal, credential, path)
