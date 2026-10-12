"""Exercise guardian dispatch/framing; real cross-account deployment remains pending."""

from unittest.mock import Mock

import pytest

from security.windows_guardian_request_pipe import GuardianRequestPipe


def fixture_pipe():
    pipe = object.__new__(GuardianRequestPipe)
    pipe.used, pipe.handle = False, 123
    pipe.owner_sid, pipe.runtime_sid = "S-1-5-21-100", "S-1-5-21-200"
    pipe.api = Mock()
    pipe._operation = Mock()
    pipe.close = Mock()
    return pipe


def test_guardian_frame_uses_role_specific_dispatch_and_server_clock(monkeypatch):
    pipe = fixture_pipe()
    raw = b'{"guardian":"fixture"}'
    pipe._read_exact = Mock(side_effect=[len(raw).to_bytes(4, "big"), raw])
    dispatch = Mock(return_value={"execution_available": False})
    monkeypatch.setattr(
        "security.windows_guardian_request_pipe.dispatch_guardian_connected", dispatch
    )
    reference = object()
    result = pipe.register_one(reference)
    args, kwargs = dispatch.call_args
    assert args == (123, raw, reference)
    assert kwargs["guardian_sid"] == pipe.owner_sid
    assert kwargs["owner_sid"] == pipe.runtime_sid
    assert kwargs["identity_api"] is pipe.api
    assert kwargs["now"].utcoffset().total_seconds() == 0
    assert not result["execution_available"]
    assert pipe.used
    pipe.close.assert_called_once()
    with pytest.raises(ValueError, match="Single-use"):
        pipe.register_one(reference)


@pytest.mark.parametrize("length", [0, 4097])
def test_bad_frame_closes_without_reference_dispatch(length):
    pipe = fixture_pipe()
    pipe._read_exact = Mock(return_value=length.to_bytes(4, "big"))
    pipe._dispatch = Mock()
    with pytest.raises(ValueError, match="frame"):
        pipe.register_one(object())
    pipe._dispatch.assert_not_called()
    pipe.close.assert_called_once()


@pytest.mark.parametrize("error", [TimeoutError, PermissionError, ValueError])
def test_timeout_identity_or_receipt_failure_closes_transport(error):
    pipe = fixture_pipe()
    pipe._read_exact = Mock(side_effect=[(2).to_bytes(4, "big"), b"{}"])
    pipe._dispatch = Mock(side_effect=error("blocked"))
    with pytest.raises(error):
        pipe.register_one(object())
    pipe.close.assert_called_once()
