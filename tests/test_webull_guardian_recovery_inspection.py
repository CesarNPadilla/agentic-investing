import hashlib
import json
from datetime import timedelta

import pytest

from security.webull_guardian_recovery_inspection import inspect_guardian_review
from tests.test_webull_guardian_reference import request, setup


def retained(tmp_path, stage):
    reference, receipt, credential, now = setup(tmp_path)
    if stage >= 1:
        reference.handle(request(reference, receipt), now=now)
    if stage >= 2:
        reference.journal.consume(receipt, credential, now=now + timedelta(seconds=1))
    if stage >= 3:
        reference.handle(
            request(reference, action="CONFIRM_REVIEW_CONSUMPTION"), now=now + timedelta(seconds=2)
        )
    return reference, now + timedelta(seconds=3)


@pytest.mark.parametrize(
    "stage,state",
    [
        (0, "NO_RETAINED_EVIDENCE_FRESHNESS_UNESTABLISHED"),
        (1, "INTENT_ONLY_RECONCILIATION_REQUIRED"),
        (2, "MATCHING_CONSUMPTION_CONFIRMATION_PENDING"),
        (3, "MATCHING_RETAINED_REVIEW_NO_RESET_AUTHORITY"),
    ],
)
def test_diagnosis_is_read_only_and_never_grants_authority(tmp_path, stage, state):
    reference, now = retained(tmp_path, stage)
    files = [reference.journal.path, reference.intent, reference.confirmation]
    before = {path: path.read_bytes() for path in files if path.exists()}
    result = inspect_guardian_review(reference, now=now)
    assert result["reference_state"] == state
    assert not result["expected_intent_digest_matched"]
    for field in [
        "files_written",
        "journal_written",
        "automatic_retry_available",
        "recovery_authorized",
        "reset_authorized",
        "execution_available",
        "trial_started",
    ]:
        assert result[field] is False
    assert {path: path.read_bytes() for path in files if path.exists()} == before


def test_expected_anchor_digest_is_checked_but_does_not_authorize_reset(tmp_path):
    reference, now = retained(tmp_path, 3)
    digest = hashlib.sha256(reference.intent.read_bytes()).hexdigest()
    result = inspect_guardian_review(reference, now=now, expected_intent_sha256=digest)
    assert result["expected_intent_digest_matched"]
    assert result["reset_authorized"] is False
    with pytest.raises(ValueError, match="digest mismatch"):
        inspect_guardian_review(reference, now=now, expected_intent_sha256="0" * 64)


@pytest.mark.parametrize(
    "mutation",
    [
        "deleted_intent",
        "changed_receipt",
        "forged_reset",
        "changed_confirmation_hash",
        "future_preparation",
        "duplicate_key",
        "nonfinite",
        "bad_id",
    ],
)
def test_altered_evidence_is_rejected_without_repair(tmp_path, mutation):
    reference, now = retained(tmp_path, 3)
    if mutation == "deleted_intent":
        reference.intent.unlink()
    elif mutation in {"forged_reset", "changed_confirmation_hash"}:
        value = json.loads(reference.confirmation.read_text())
        value["reset_authorized" if mutation == "forged_reset" else "intent_sha256"] = (
            True if mutation == "forged_reset" else "0" * 64
        )
        reference.confirmation.write_text(json.dumps(value))
    else:
        value = json.loads(reference.intent.read_text())
        if mutation == "changed_receipt":
            value["receipt_sha256"] = "0" * 64
        elif mutation == "future_preparation":
            value["prepared_at"] = (now + timedelta(seconds=1)).isoformat()
        elif mutation == "bad_id":
            value["request_id"] = "not-an-identifier"
        raw = json.dumps(value)
        if mutation == "duplicate_key":
            raw = '{"request_id":"duplicate",' + raw[1:]
        elif mutation == "nonfinite":
            raw = raw[:-1] + ',"extra":NaN}'
        reference.intent.write_text(raw)
    with pytest.raises(ValueError):
        inspect_guardian_review(reference, now=now)


def test_deleted_consumption_with_confirmation_is_rejected(tmp_path):
    import sqlite3

    reference, now = retained(tmp_path, 3)
    with sqlite3.connect(reference.journal.path) as db:
        db.execute("DELETE FROM reviews")
    with pytest.raises(ValueError, match="without matching"):
        inspect_guardian_review(reference, now=now)


def test_deleted_all_evidence_cannot_match_protected_prior_digest(tmp_path):
    import sqlite3

    reference, now = retained(tmp_path, 3)
    digest = hashlib.sha256(reference.intent.read_bytes()).hexdigest()
    reference.intent.unlink()
    reference.confirmation.unlink()
    with sqlite3.connect(reference.journal.path) as db:
        db.execute("DELETE FROM reviews")
    with pytest.raises(ValueError, match="Missing guardian intent"):
        inspect_guardian_review(reference, now=now, expected_intent_sha256=digest)


def test_evidence_change_during_read_blocks_result(tmp_path, monkeypatch):
    reference, now = retained(tmp_path, 3)
    original = reference._rows
    calls = 0

    def changed():
        nonlocal calls
        calls += 1
        return original() if calls == 1 else []

    monkeypatch.setattr(reference, "_rows", changed)
    with pytest.raises(ValueError, match="changed during inspection"):
        inspect_guardian_review(reference, now=now)
