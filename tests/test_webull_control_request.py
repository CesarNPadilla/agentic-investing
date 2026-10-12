import json

import pytest

from security.webull_control_request import diagnostic_receipt, parse_control_request


def payload():
    return {
        "schema_version": "webull-control-request-v1",
        "action": "REQUEST_RESET_REVIEW",
        "account_binding_sha256": "a" * 64,
        "expected_state_sha256": "b" * 64,
        "request_id": "8d60999d-8cf5-4cfa-b9ec-aa40c20732f6",
    }


def parse(value):
    return parse_control_request(json.dumps(value).encode(), expected_binding="a" * 64)


def test_reset_review_is_never_reset_or_approval():
    receipt = diagnostic_receipt(parse(payload()))
    assert receipt["request_parsed"]
    for key in (
        "caller_authenticated",
        "owner_approval_verified",
        "state_digest_verified",
        "request_replay_checked",
        "controller_admitted",
        "reset_performed",
        "execution_available",
        "trial_started",
    ):
        assert receipt[key] is False


@pytest.mark.parametrize(
    "change",
    [
        {"action": "CLEAR_LATCH"},
        {"action": "SUBMIT_ORDER"},
        {"owner_approval_verified": True},
        {"execution_available": True},
        {"caller_sid": "S-1-forged"},
        {"account_binding_sha256": "c" * 64},
        {"expected_state_sha256": "unknown"},
        {"request_id": "not-a-nonce"},
        {"request_id": "00000000-0000-0000-0000-000000000000"},
    ],
)
def test_forged_authority_and_malformed_identity_rejected(change):
    with pytest.raises(ValueError, match="Untrusted control request rejected"):
        parse(payload() | change)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"action":"REQUEST_RESET_REVIEW","action":"CLEAR_LATCH"}',
        b"[]",
        b"\xff",
        b'{"value":NaN}',
        b"x" * 4097,
    ],
)
def test_ambiguous_or_invalid_bytes_rejected(raw):
    with pytest.raises(ValueError):
        parse_control_request(raw, expected_binding="a" * 64)


def test_same_request_can_parse_twice_but_is_never_admitted():
    # Persistent replay prevention belongs to the future protected controller.
    assert diagnostic_receipt(parse(payload())) == diagnostic_receipt(parse(payload()))
    assert diagnostic_receipt(parse(payload()))["request_replay_checked"] is False


def test_readonly_action_is_still_untrusted():
    receipt = diagnostic_receipt(parse(payload() | {"action": "REQUEST_READONLY_SNAPSHOT"}))
    assert not receipt["controller_admitted"] and not receipt["execution_available"]
