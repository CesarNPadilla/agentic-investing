import json
from uuid import uuid4

import pytest

from security.webull_pipe_registration import register_connected_request
from security.webull_request_journal import RequestJournal

OWNER = "S-1-5-21-100-200-300-1001"
RUNTIME = "S-1-5-21-100-200-300-1002"


def raw():
    return json.dumps(
        {
            "schema_version": "webull-control-request-v1",
            "action": "REQUEST_RESET_REVIEW",
            "account_binding_sha256": "a" * 64,
            "expected_state_sha256": "b" * 64,
            "request_id": str(uuid4()),
        }
    ).encode()


class Identity:
    def __init__(self, sid, *, succeeds=True):
        self.sid, self.succeeds, self.impersonating = sid, succeeds, False

    def impersonate(self, handle):
        self.impersonating = self.succeeds
        return self.succeeds

    def read_identity(self):
        assert self.impersonating
        return self.sid

    def revert(self):
        self.impersonating = False
        return True


@pytest.mark.parametrize("sid,role", [(OWNER, "OWNER"), (RUNTIME, "RUNTIME")])
def test_scoped_identity_registers_only_after_reversion(tmp_path, sid, role):
    api = Identity(sid)
    journal = RequestJournal.initialize(
        tmp_path / "journal.sqlite", "a" * 64, state_digest="b" * 64
    )

    class GuardedJournal:
        def register(self, request, **kwargs):
            assert not api.impersonating
            return journal.register(request, **kwargs)

    request = raw()
    receipt = register_connected_request(
        1, request, GuardedJournal(), owner_sid=OWNER, runtime_sid=RUNTIME, identity_api=api
    )
    assert receipt["observed_caller_role"] == role and receipt["request_registered"]
    assert not receipt["owner_approval_verified"] and not receipt["controller_admitted"]
    assert not receipt["reset_performed"] and not receipt["execution_available"]
    with pytest.raises(ValueError, match="replay"):
        register_connected_request(
            1, request, GuardedJournal(), owner_sid=OWNER, runtime_sid=RUNTIME, identity_api=api
        )


@pytest.mark.parametrize("sid,succeeds", [("S-1-5-21-100-200-300-9999", True), (OWNER, False)])
def test_unknown_or_unobservable_identity_never_reaches_journal(tmp_path, sid, succeeds):
    journal = RequestJournal.initialize(
        tmp_path / "journal.sqlite", "a" * 64, state_digest="b" * 64
    )
    with pytest.raises((OSError, PermissionError)):
        register_connected_request(
            1,
            raw(),
            journal,
            owner_sid=OWNER,
            runtime_sid=RUNTIME,
            identity_api=Identity(sid, succeeds=succeeds),
        )
    assert journal.verify()["retained_requests"] == 0


def test_owner_and_runtime_cannot_be_the_same_identity(tmp_path):
    with pytest.raises(ValueError, match="Distinct"):
        register_connected_request(1, raw(), None, owner_sid=OWNER, runtime_sid=OWNER)
