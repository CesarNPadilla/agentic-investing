import copy
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from security.webull_review_journal import ReviewJournal
from tests.test_webull_review_signature import signed_review


def test_consumption_survives_restart_without_authorizing_reset(tmp_path):
    receipt, credential, envelope, now, _ = signed_review()
    path = tmp_path / "review.sqlite"
    journal = ReviewJournal.initialize(path, expected_envelope=envelope)
    result = journal.consume(receipt, credential, now=now)
    assert result["review_evidence_consumed"]
    assert not result["approval_consumed"] and not result["reset_authorized"]
    reopened = ReviewJournal(path, expected_envelope=envelope)
    assert reopened.verify(credential)["retained_review_count"] == 1
    with pytest.raises(ValueError, match="replay"):
        reopened.consume(receipt, credential, now=now)
    with pytest.raises(FileExistsError):
        ReviewJournal.initialize(path, expected_envelope=envelope)


def test_concurrent_duplicate_is_consumed_once(tmp_path):
    receipt, credential, envelope, now, _ = signed_review()
    journal = ReviewJournal.initialize(tmp_path / "review.sqlite", expected_envelope=envelope)

    def consume(_):
        try:
            journal.consume(receipt, credential, now=now)
            return "consumed"
        except ValueError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sorted(pool.map(consume, range(4))) == ["consumed"] + ["rejected"] * 3
    assert journal.verify(credential)["retained_review_count"] == 1


@pytest.mark.parametrize("failure", ["signature", "expired", "foreign", "claimed_verified"])
def test_rejected_review_leaves_journal_unconsumed(tmp_path, failure):
    receipt, credential, envelope, now, _ = signed_review()
    journal = ReviewJournal.initialize(tmp_path / "review.sqlite", expected_envelope=envelope)
    changed = copy.deepcopy(receipt)
    verify_at = now
    if failure == "signature":
        changed["assertion"]["response"]["signature"] = "aW52YWxpZA"
    elif failure == "expired":
        verify_at += timedelta(seconds=300)
    elif failure == "foreign":
        changed["envelope"]["account_binding_sha256"] = "c" * 64
    else:
        changed = {"review_signature_verified": True}
    with pytest.raises(ValueError):
        journal.consume(changed, credential, now=verify_at)
    assert journal.verify(credential)["retained_review_count"] == 0
    assert journal.consume(receipt, credential, now=now)["review_evidence_consumed"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("receipt_sha256", "c" * 64),
        ("review_id", "changed"),
        ("consumed_at", "2026-10-08T17:00:00+00:00"),
    ],
)
def test_retained_tampering_blocks_verification_and_new_consumption(tmp_path, field, value):
    receipt, credential, envelope, now, _ = signed_review()
    journal = ReviewJournal.initialize(tmp_path / "review.sqlite", expected_envelope=envelope)
    journal.consume(receipt, credential, now=now)
    with sqlite3.connect(journal.path) as db:
        db.execute(f"UPDATE reviews SET {field}=?", (value,))
    with pytest.raises(ValueError):
        journal.verify(credential)
    with pytest.raises(ValueError):
        journal.consume(receipt, credential, now=now)


def test_changed_context_and_missing_journal_fail_closed(tmp_path):
    _, credential, envelope, _, _ = signed_review()
    path = tmp_path / "review.sqlite"
    journal = ReviewJournal(path, expected_envelope=envelope)
    with pytest.raises(sqlite3.OperationalError):
        journal.verify(credential)
    assert not path.exists()
    ReviewJournal.initialize(path, expected_envelope=envelope)
    changed = envelope.model_copy(update={"reset_review_sha256": "c" * 64})
    with pytest.raises(ValueError, match="context"):
        ReviewJournal(path, expected_envelope=changed).verify(credential)
