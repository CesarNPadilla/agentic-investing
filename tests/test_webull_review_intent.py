import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fido2.utils import websafe_encode

from security.webull_review_intent import ReviewIntent
from security.webull_review_journal import ReviewJournal
from tests.test_webull_review_signature import signed_review


def setup(tmp_path):
    receipt, credential, envelope, now, _ = signed_review()
    (tmp_path / "state").mkdir()
    (tmp_path / "reference").mkdir()
    journal = ReviewJournal.initialize(tmp_path / "state/review.sqlite", expected_envelope=envelope)
    guard = ReviewIntent.initialize(journal, tmp_path / "reference/intent.json", credential)
    return guard, receipt, credential, now


def test_write_ahead_reference_survives_restart_without_authority(tmp_path):
    guard, receipt, credential, now = setup(tmp_path)
    result = guard.consume(receipt, credential, now=now)
    assert result["write_ahead_intent_retained"] and not result["reset_authorized"]
    reopened = ReviewIntent(guard.journal, guard.intent)
    assert reopened.inspect(credential)["state"] == "CONSUMED_REVIEW_MATCHES_REFERENCE"
    with pytest.raises(ValueError):
        reopened.consume(receipt, credential, now=now)


def test_failure_after_intent_blocks_retry_even_without_sqlite_consumption(tmp_path, monkeypatch):
    guard, receipt, credential, now = setup(tmp_path)

    def fail(*args, **kwargs):
        raise OSError("simulated storage failure")

    monkeypatch.setattr(guard.journal, "consume", fail)
    with pytest.raises(OSError):
        guard.consume(receipt, credential, now=now)
    assert guard.inspect(credential)["state"] == "INCOMPLETE_OR_ROLLED_BACK_BLOCKED"
    assert guard.journal.verify(credential)["retained_review_count"] == 0
    with pytest.raises(ValueError):
        guard.consume(receipt, credential, now=now)


def test_deleted_sqlite_consumption_cannot_replay_against_retained_intent(tmp_path):
    guard, receipt, credential, now = setup(tmp_path)
    guard.consume(receipt, credential, now=now)
    with sqlite3.connect(guard.journal.path) as db:
        db.execute("DELETE FROM reviews")
    assert guard.inspect(credential)["state"] == "INCOMPLETE_OR_ROLLED_BACK_BLOCKED"
    with pytest.raises(ValueError):
        guard.consume(receipt, credential, now=now)


def test_concurrent_submissions_leave_one_consumed_reference(tmp_path):
    guard, receipt, credential, now = setup(tmp_path)

    def attempt(_):
        try:
            guard.consume(receipt, credential, now=now)
            return True
        except (ValueError, FileExistsError):
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(attempt, range(4))) == 1
    assert guard.inspect(credential)["state"] == "CONSUMED_REVIEW_MATCHES_REFERENCE"


@pytest.mark.parametrize("failure", ["missing", "changed", "truncated_intent", "forged_signature"])
def test_invalid_reference_or_assertion_never_grants_recovery(tmp_path, failure):
    guard, receipt, credential, now = setup(tmp_path)
    if failure == "missing":
        guard.bootstrap.unlink()
    elif failure == "changed":
        guard.bootstrap.write_text(json.dumps({"reset_authorized": True}))
    elif failure == "truncated_intent":
        guard.intent.write_text("{")
    else:
        receipt["assertion"]["response"]["signature"] = "aW52YWxpZA"
    with pytest.raises((ValueError, FileNotFoundError)):
        guard.consume(receipt, credential, now=now)
    assert guard.journal.verify(credential)["retained_review_count"] == 0
    if failure == "forged_signature":
        assert not guard.intent.exists()


def test_missing_journal_is_not_recreated_and_colliding_directory_rejected(tmp_path):
    guard, _, credential, _ = setup(tmp_path)
    guard.journal.path.unlink()
    with pytest.raises(sqlite3.OperationalError):
        guard.inspect(credential)
    assert not guard.journal.path.exists()
    with pytest.raises(ValueError):
        ReviewIntent(guard.journal, guard.journal.path.with_suffix(".json"))


@pytest.mark.parametrize(
    "boundary,code,expected_state",
    [
        ("before", 73, "INCOMPLETE_OR_ROLLED_BACK_BLOCKED"),
        ("after", 74, "CONSUMED_REVIEW_MATCHES_REFERENCE"),
    ],
)
def test_abrupt_process_exit_preserves_intent_and_blocks_replay(
    tmp_path, boundary, code, expected_state
):
    guard, receipt, credential, now = setup(tmp_path)
    payload = tmp_path / "synthetic-input.json"
    payload.write_text(
        json.dumps(
            {
                "receipt": receipt,
                "credential": websafe_encode(bytes(credential)),
                "envelope": guard.journal.expected_envelope.model_dump(mode="json"),
                "now": now.isoformat(),
            }
        )
    )
    script = r"""
import json,sys,os
from datetime import datetime
from fido2.utils import websafe_decode
from fido2.webauthn import AttestedCredentialData
from security.webull_review_signature import ReviewEnvelope
from security.webull_review_journal import ReviewJournal
from security.webull_review_intent import ReviewIntent
from pathlib import Path
p=json.loads(Path(sys.argv[1]).read_text())
j=ReviewJournal(sys.argv[2],expected_envelope=ReviewEnvelope.model_validate(p['envelope']))
g=ReviewIntent(j,sys.argv[3])
original=j.consume
def crash(*args,**kwargs):
 if sys.argv[4]=='after':original(*args,**kwargs)
 os._exit(74 if sys.argv[4]=='after' else 73)
j.consume=crash
g.consume(p['receipt'],AttestedCredentialData(websafe_decode(p['credential'])),now=datetime.fromisoformat(p['now']))
"""
    child = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            script,
            str(payload),
            str(guard.journal.path),
            str(guard.intent),
            boundary,
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        timeout=15,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert child.returncode == code, child.stderr
    assert guard.intent.exists()
    assert guard.inspect(credential)["state"] == expected_state
    with pytest.raises(ValueError):
        guard.consume(receipt, credential, now=now)
