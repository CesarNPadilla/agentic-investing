"""Native engineering-token exchange; no actual guardian-account qualification."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

from security.windows_guardian_exchange_client import GuardianExchangeClient
from security.windows_guardian_exchange_pipe import GuardianExchangePipe
from security.windows_guardian_request_pipe import GuardianRequestPipe
from security.windows_pipe_identity import NativePipeIdentity


def test_native_client_authenticates_server_and_completes_receipt_handshake(monkeypatch):
    sid = NativePipeIdentity().read_process_identity()
    pipe = GuardianExchangePipe(guardian_sid=sid, owner_sid="S-1-5-21-100-200-300-9999")
    dispatch = Mock(return_value={"execution_available": False, "reset_authorized": False})
    monkeypatch.setattr(GuardianRequestPipe, "_dispatch", dispatch)
    client = GuardianExchangeClient(name=pipe.name, guardian_sid=sid)
    with ThreadPoolExecutor(max_workers=1) as pool:
        server = pool.submit(pipe.register_one, object())
        try:
            response = client.exchange(b"{}")
            assert response == server.result(timeout=6)
            assert response["execution_available"] is False
            assert client.handle is None and pipe.handle is None
            with pytest.raises(ValueError, match="Single-use"):
                client.exchange(b"{}")
        finally:
            client.close()
    dispatch.assert_called_once()


def test_wrong_server_identity_rejected_before_any_request_bytes(monkeypatch):
    sid = NativePipeIdentity().read_process_identity()
    dummy = "S-1-5-21-100-200-300-9999"
    pipe = GuardianExchangePipe(guardian_sid=sid, owner_sid=dummy)
    dispatch = Mock()
    monkeypatch.setattr(GuardianRequestPipe, "_dispatch", dispatch)
    client = GuardianExchangeClient(name=pipe.name, guardian_sid=dummy)
    with ThreadPoolExecutor(max_workers=1) as pool:
        server = pool.submit(pipe.register_one, object(), timeout_seconds=1)
        with pytest.raises(PermissionError, match="identity"):
            client.exchange(b"SYNTHETIC_SHOULD_NEVER_SEND")
        with pytest.raises(OSError):
            server.result(timeout=2)
    dispatch.assert_not_called()
    assert client.handle is None and pipe.handle is None


@pytest.mark.parametrize("name", ["remote\\pipe", "AgenticRequest-invalid", "", None])
def test_untrusted_pipe_names_are_rejected_before_open(name):
    with pytest.raises(ValueError, match="name"):
        GuardianExchangeClient(name=name, guardian_sid="S-1-5-21-100")


@pytest.mark.parametrize("timeout", [0, 6, float("nan"), True, "5"])
def test_invalid_deadline_does_not_open_client(timeout):
    client = GuardianExchangeClient(name="AgenticRequest-" + "a" * 32, guardian_sid="S-1-5-21-100")
    with pytest.raises(ValueError, match="deadline"):
        client.exchange(b"{}", timeout_seconds=timeout)
    assert not client.used and client.handle is None
