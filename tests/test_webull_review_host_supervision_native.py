"""Engineering-token interrupted-host retention; synthetic signatures and pipe dispatch."""

import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from security.webull_guardian_review_host import GuardianReviewHost
from security.windows_review_process_supervisor import supervise_review_process
from tests.test_webull_guardian_reference import setup

CHILD = r"""
import json,sys,time
from datetime import datetime
from pathlib import Path
from fido2.webauthn import AttestedCredentialData
from security.webull_guardian_reference import GuardianReference
from security.webull_guardian_review_host import GuardianReviewHost
from security.webull_review_journal import ReviewJournal
from security.webull_review_signature import ReviewEnvelope
from tests.test_webull_guardian_reference import request
root=Path(sys.argv[1]);phase=sys.argv[2]
config=json.loads((root/'config.json').read_text())
now=datetime.fromisoformat(config['now'])
envelope=ReviewEnvelope.model_validate(config['envelope'])
credential=AttestedCredentialData(bytes.fromhex(config['credential']))
journal=ReviewJournal(root/'owner/review.sqlite',expected_envelope=envelope)
reference=GuardianReference(root/'guardian',journal,credential)
class Pipe:
 name='synthetic-no-native-pipe'
 def register_one(self,endpoint,**kwargs):
  endpoint.handle(request(reference,config['receipt']),now=now)
  if phase=='consumed':journal.consume(config['receipt'],credential,now=now)
 def close(self):pass
host=GuardianReviewHost(reference,guardian_sid='synthetic',owner_sid='synthetic',
 provisioned_envelope_sha256=envelope.digest(),now=lambda:now,pipe_factory=Pipe)
def publish(value):
 if (phase=='start' and value['action']=='PREPARE_REVIEW_REFERENCE') or (phase!='start' and value['action']=='CONFIRM_REVIEW_CONSUMPTION'):
  (root/'blocked.json').write_text(json.dumps(value))
  time.sleep(60)
host.run(publish)
"""

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Native Windows job required")


@pytest.mark.parametrize("phase", ["start", "intent", "consumed"])
@pytest.mark.parametrize("termination", ["stop", "deadline"])
def test_interrupted_host_keeps_evidence_and_blocks_restart(tmp_path, phase, termination):
    reference, receipt, credential, now = setup(tmp_path)
    config = {
        "envelope": reference.journal.expected_envelope.model_dump(mode="json"),
        "credential": bytes(credential).hex(),
        "receipt": receipt,
        "now": now.isoformat(),
    }
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    marker = tmp_path / "blocked.json"
    result = supervise_review_process(
        Path(sys.executable),
        ["-B", "-c", CHILD, str(tmp_path), phase],
        Path(__file__).resolve().parents[1],
        seconds=5,
        stop_requested=lambda: termination == "stop" and marker.exists(),
    )
    assert marker.exists(), "Child did not reach the selected host phase"
    expected = "STOP_REQUESTED" if termination == "stop" else "DEADLINE_TERMINATED"
    assert result["termination"] == expected and result["process_tree_active"] == 0
    assert not result["execution_available"] and not result["reset_authorized"]
    assert (reference.directory / "host-start.json").exists()
    assert not (reference.directory / "host-terminal.json").exists()
    assert reference.intent.exists() == (phase != "start")
    assert not reference.confirmation.exists()
    assert reference.journal.verify(credential)["retained_review_count"] == (phase == "consumed")
    retained = {p: p.read_bytes() for p in reference.directory.iterdir()}
    journal_before = reference.journal.path.read_bytes()
    host = GuardianReviewHost(
        reference,
        guardian_sid="synthetic",
        owner_sid="synthetic",
        provisioned_envelope_sha256=reference.journal.expected_envelope.digest(),
        now=lambda: now,
        pipe_factory=Mock(side_effect=AssertionError("Restart must not open transport")),
    )
    with pytest.raises((ValueError, FileExistsError)):
        host.run(Mock(side_effect=AssertionError("Restart must not publish")))
    assert {p: p.read_bytes() for p in reference.directory.iterdir()} == retained
    assert reference.journal.path.read_bytes() == journal_before
