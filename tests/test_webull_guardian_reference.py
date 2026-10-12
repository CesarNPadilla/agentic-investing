import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest

from security.webull_guardian_bridge import dispatch_guardian_connected
from security.webull_guardian_reference import GuardianReference, parse_guardian_request
from security.webull_review_journal import ReviewJournal
from tests.test_webull_review_signature import signed_review


def setup(tmp_path):
    receipt, credential, envelope, now, _ = signed_review()
    (tmp_path / "owner").mkdir()
    (tmp_path / "guardian").mkdir()
    journal = ReviewJournal.initialize(tmp_path / "owner/review.sqlite", expected_envelope=envelope)
    reference = GuardianReference(tmp_path / "guardian", journal, credential)
    return reference, receipt, credential, now


def request(reference, receipt=None, *, action="PREPARE_REVIEW_REFERENCE"):
    value = {
        "schema_version": "webull-guardian-request-v1",
        "action": action,
        "request_id": str(uuid4()),
        "envelope_sha256": reference.journal.expected_envelope.digest(),
    }
    if receipt is not None:
        value["signed_receipt"] = receipt
    return json.dumps(value).encode()


def test_guardian_only_prepares_and_confirms_owner_written_journal(tmp_path):
    reference, receipt, credential, now = setup(tmp_path)
    result = reference.handle(request(reference, receipt), now=now)
    assert result["reference_state"] == "INTENT_RETAINED_OWNER_JOURNAL_NOT_CONSUMED"
    assert reference.journal.verify(credential)["retained_review_count"] == 0
    with pytest.raises(ValueError):
        reference.handle(request(reference, action="CONFIRM_REVIEW_CONSUMPTION"), now=now)
    reference.journal.consume(receipt, credential, now=now + timedelta(seconds=1))
    result = reference.handle(
        request(reference, action="CONFIRM_REVIEW_CONSUMPTION"), now=now + timedelta(seconds=2)
    )
    assert result["reference_state"] == "MATCHING_OWNER_CONSUMPTION_CONFIRMED"
    for field in [
        "owner_journal_written_by_guardian",
        "recovery_authorized",
        "reset_authorized",
        "execution_available",
        "trial_started",
    ]:
        assert result[field] is False
    with pytest.raises(FileExistsError):
        reference.handle(
            request(reference, action="CONFIRM_REVIEW_CONSUMPTION"), now=now + timedelta(seconds=3)
        )
    with pytest.raises(ValueError):
        reference.handle(request(reference, receipt), now=now)


@pytest.mark.parametrize("failure", ["signature", "expired", "forged_flag"])
def test_invalid_signed_request_does_not_create_intent(tmp_path, failure):
    reference, receipt, _, now = setup(tmp_path)
    if failure == "signature":
        receipt["assertion"]["response"]["signature"] = "aW52YWxpZA"
    elif failure == "expired":
        now += timedelta(seconds=300)
    else:
        receipt["reset_authorized"] = True
    with pytest.raises(ValueError):
        reference.handle(request(reference, receipt), now=now)
    assert not reference.intent.exists()


@pytest.mark.parametrize(
    "failure", ["deleted_owner_row", "changed_intent", "future_owner_consumption"]
)
def test_reference_mismatch_or_rollback_never_confirms(tmp_path, failure):
    reference, receipt, credential, now = setup(tmp_path)
    reference.handle(request(reference, receipt), now=now)
    reference.journal.consume(receipt, credential, now=now + timedelta(seconds=1))
    if failure == "deleted_owner_row":
        with sqlite3.connect(reference.journal.path) as db:
            db.execute("DELETE FROM reviews")
    elif failure == "changed_intent":
        value = json.loads(reference.intent.read_text())
        value["receipt_sha256"] = "c" * 64
        reference.intent.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        reference.handle(request(reference, action="CONFIRM_REVIEW_CONSUMPTION"), now=now)
    assert not reference.confirmation.exists()
    with pytest.raises(ValueError):
        reference.handle(request(reference, receipt), now=now)


def test_concurrent_reference_preparation_is_one_use_without_owner_journal_writes(tmp_path):
    reference, receipt, credential, now = setup(tmp_path)

    def attempt(_):
        try:
            reference.handle(request(reference, receipt), now=now)
            return True
        except (ValueError, FileExistsError):
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(attempt, range(4))) == 1
    assert reference.journal.verify(credential)["retained_review_count"] == 0


@pytest.mark.parametrize(
    "change",
    [
        "extra_identity",
        "extra_path",
        "reset",
        "digest",
        "identifier",
        "duplicate",
        "nonfinite",
        "oversize",
        "utf8",
    ],
)
def test_untrusted_wire_claims_rejected(tmp_path, change):
    reference, receipt, _, _ = setup(tmp_path)
    value = json.loads(request(reference, receipt))
    if change == "extra_identity":
        value["owner_sid"] = "S-1-5-21-1"
    elif change == "extra_path":
        value["journal_path"] = "C:/attacker"
    elif change == "reset":
        value["action"] = "RESET_DAILY_LOSS"
    elif change == "digest":
        value["envelope_sha256"] = "c" * 64
    elif change == "identifier":
        value["request_id"] = str(uuid4()).upper()
    raw = json.dumps(value).encode()
    if change == "duplicate":
        raw = b'{"action":"PREPARE_REVIEW_REFERENCE",' + raw[1:]
    elif change == "nonfinite":
        raw = raw[:-1] + b',"extra":NaN}'
    elif change == "oversize":
        raw = b"x" * 4097
    elif change == "utf8":
        raw = b"\xff"
    with pytest.raises(ValueError):
        parse_guardian_request(raw, reference.journal.expected_envelope.digest())


class Identity:
    def __init__(self, caller="S-1-5-21-2", process="S-1-5-21-1"):
        self.caller, self.process, self.calls = caller, process, []

    def read_process_identity(self):
        return self.process

    def impersonate(self, handle):
        self.calls.append("impersonate")
        return True

    def read_identity(self):
        self.calls.append("read")
        return self.caller

    def revert(self):
        self.calls.append("revert")
        return True


def test_bridge_restores_guardian_identity_before_reference_write():
    identity = Identity()

    class Endpoint:
        def handle(self, raw, *, now):
            assert identity.calls == ["impersonate", "read", "revert"]
            return {"reset_authorized": False}

    _, _, _, now, _ = signed_review()
    result = dispatch_guardian_connected(
        1,
        b"fixture",
        Endpoint(),
        guardian_sid="S-1-5-21-1",
        owner_sid="S-1-5-21-2",
        now=now,
        identity_api=identity,
    )
    assert result["owner_pipe_identity_observed"] and not result["reset_authorized"]


@pytest.mark.parametrize(
    "caller,process", [("S-1-5-21-3", "S-1-5-21-1"), ("S-1-5-21-2", "S-1-5-21-2")]
)
def test_other_caller_or_wrong_guardian_process_never_reaches_reference(caller, process):
    class Endpoint:
        def handle(self, *args, **kwargs):
            raise AssertionError("Unauthorized reference write")

    _, _, _, now, _ = signed_review()
    with pytest.raises(PermissionError):
        dispatch_guardian_connected(
            1,
            b"fixture",
            Endpoint(),
            guardian_sid="S-1-5-21-1",
            owner_sid="S-1-5-21-2",
            now=now,
            identity_api=Identity(caller, process),
        )
