import json
from unittest.mock import Mock

import pytest

from security.windows_guardian_exchange_pipe import GuardianExchangePipe
from security.windows_guardian_request_pipe import GuardianRequestPipe


def setup(monkeypatch, *, read=b"\x01", counts=None):
    pipe = object.__new__(GuardianExchangePipe)
    pipe.api = Mock()
    pipe.handle, pipe.response_deadline = 123, 456
    pipe._read_exact = Mock(return_value=read)
    result = {"execution_available": False, "reset_authorized": False}
    monkeypatch.setattr(GuardianRequestPipe, "_dispatch", lambda *_: result)
    size = len(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()) + 4
    pipe._operation = Mock(side_effect=counts or [size])
    return pipe, result, size


def test_reply_delivery_requires_client_receipt_and_uses_same_deadline(monkeypatch):
    pipe, result, _ = setup(monkeypatch)
    assert pipe._dispatch(b"{}", object()) == result
    assert pipe._operation.call_args.args[1] == 456
    pipe._read_exact.assert_called_once_with(1, 456)


def test_partial_write_is_completed_within_original_deadline(monkeypatch):
    pipe, result, size = setup(monkeypatch)
    pipe._operation.side_effect = [2, size - 2]
    assert pipe._dispatch(b"{}", object()) == result
    assert pipe._operation.call_count == 2


@pytest.mark.parametrize("read", [b"", b"\x00", b"bad"])
def test_missing_or_invalid_client_receipt_blocks_success(monkeypatch, read):
    pipe, _, _ = setup(monkeypatch, read=read)
    with pytest.raises(ValueError, match="receipt"):
        pipe._dispatch(b"{}", object())


@pytest.mark.parametrize("count", [0, -1, 9999])
def test_invalid_write_result_blocks_success(monkeypatch, count):
    pipe, _, _ = setup(monkeypatch, counts=[count])
    with pytest.raises(OSError):
        pipe._dispatch(b"{}", object())
    pipe._read_exact.assert_not_called()


def test_reply_timeout_preserves_transport_error(monkeypatch):
    pipe, _, _ = setup(monkeypatch)
    pipe._read_exact.side_effect = TimeoutError("Synthetic disconnected client")
    with pytest.raises(TimeoutError):
        pipe._dispatch(b"{}", object())
