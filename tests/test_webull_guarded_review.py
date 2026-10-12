import json

import pytest

from security.webull_guarded_review import consume_guarded_review
from tests.test_webull_guardian_reference import setup


def exchange_for(reference, now, *, change=None, fail=None):
    def exchange(raw):
        action = json.loads(raw)["action"]
        if fail == action:
            raise OSError("Synthetic unavailable transport")
        response = reference.handle(raw, now=now) | {"owner_pipe_identity_observed": True}
        if change is not None:
            change(response, action)
        return response

    return exchange


def test_ordered_retention_and_confirmation_with_real_synthetic_signature(tmp_path):
    reference, receipt, credential, now = setup(tmp_path)
    result = consume_guarded_review(
        receipt,
        credential,
        reference.journal,
        exchange=exchange_for(reference, now),
        now=lambda: now,
    )
    assert result["guardian_reference_confirmed"] is True
    assert reference.intent.exists() and reference.confirmation.exists()
    assert reference.journal.verify(credential)["retained_review_count"] == 1
    assert result["reset_authorized"] is False and result["execution_available"] is False
    with pytest.raises(ValueError, match="already retained"):
        consume_guarded_review(
            receipt,
            credential,
            reference.journal,
            exchange=exchange_for(reference, now),
            now=lambda: now,
        )


@pytest.mark.parametrize("phase", ["PREPARE_REVIEW_REFERENCE", "CONFIRM_REVIEW_CONSUMPTION"])
def test_transport_failure_preserves_partial_state_without_retry(tmp_path, phase):
    reference, receipt, credential, now = setup(tmp_path)
    with pytest.raises(OSError):
        consume_guarded_review(
            receipt,
            credential,
            reference.journal,
            exchange=exchange_for(reference, now, fail=phase),
            now=lambda: now,
        )
    retained = phase == "CONFIRM_REVIEW_CONSUMPTION"
    assert reference.intent.exists() is retained
    assert reference.journal.verify(credential)["retained_review_count"] == int(retained)
    assert not reference.confirmation.exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("request_id", "foreign"),
        ("reference_state", "foreign"),
        ("owner_pipe_identity_observed", False),
        ("owner_journal_written_by_guardian", True),
        ("reset_authorized", True),
        ("execution_available", True),
        ("trial_started", True),
        ("recovery_authorized", True),
        ("extra", False),
    ],
)
@pytest.mark.parametrize("phase", ["PREPARE_REVIEW_REFERENCE", "CONFIRM_REVIEW_CONSUMPTION"])
def test_invalid_acknowledgement_never_reports_success(tmp_path, field, value, phase):
    reference, receipt, credential, now = setup(tmp_path)

    def change(response, action):
        if action == phase:
            response[field] = value

    with pytest.raises(ValueError, match="acknowledgement"):
        consume_guarded_review(
            receipt,
            credential,
            reference.journal,
            exchange=exchange_for(reference, now, change=change),
            now=lambda: now,
        )
    assert reference.intent.exists()
    assert reference.journal.verify(credential)["retained_review_count"] == int(
        phase == "CONFIRM_REVIEW_CONSUMPTION"
    )
    assert reference.confirmation.exists() is (phase == "CONFIRM_REVIEW_CONSUMPTION")


def test_bad_signature_never_calls_transport_or_consumes(tmp_path):
    reference, receipt, credential, now = setup(tmp_path)
    receipt["assertion"]["response"]["signature"] = "aW52YWxpZA"

    def forbidden(_):
        pytest.fail("Invalid signature reached guardian exchange")

    with pytest.raises(ValueError):
        consume_guarded_review(
            receipt, credential, reference.journal, exchange=forbidden, now=lambda: now
        )
    assert not reference.intent.exists()
    assert reference.journal.verify(credential)["retained_review_count"] == 0


def test_journal_failure_leaves_intent_and_blocks_fresh_attempt(tmp_path, monkeypatch):
    reference, receipt, credential, now = setup(tmp_path)

    def fail(*_, **__):
        raise OSError("Synthetic journal failure")

    monkeypatch.setattr(reference.journal, "consume", fail)
    with pytest.raises(OSError):
        consume_guarded_review(
            receipt,
            credential,
            reference.journal,
            exchange=exchange_for(reference, now),
            now=lambda: now,
        )
    assert reference.intent.exists() and not reference.confirmation.exists()
    with pytest.raises(ValueError, match="inconsistent"):
        consume_guarded_review(
            receipt,
            credential,
            reference.journal,
            exchange=exchange_for(reference, now),
            now=lambda: now,
        )
