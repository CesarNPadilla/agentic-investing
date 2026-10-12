import pytest

from security.windows_pipe_identity import identify_pipe_client


class FakeApi:
    def __init__(self, *, impersonates=True, reverts=True, read_error=False):
        self.impersonates, self.reverts, self.read_error = impersonates, reverts, read_error
        self.calls = []

    def impersonate(self, handle):
        self.calls.append("impersonate")
        return self.impersonates

    def read_identity(self):
        self.calls.append("read")
        if self.read_error:
            raise OSError("token unavailable")
        return "S-1-5-21-test"

    def revert(self):
        self.calls.append("revert")
        return self.reverts


def test_identity_is_returned_only_after_reversion():
    api = FakeApi()
    assert identify_pipe_client(123, api=api) == "S-1-5-21-test"
    assert api.calls == ["impersonate", "read", "revert"]


def test_failed_impersonation_never_reads_server_identity_as_client():
    api = FakeApi(impersonates=False)
    with pytest.raises(OSError, match="authentication failed"):
        identify_pipe_client(123, api=api)
    assert api.calls == ["impersonate"]


def test_failed_token_read_still_reverts():
    api = FakeApi(read_error=True)
    with pytest.raises(OSError, match="token unavailable"):
        identify_pipe_client(123, api=api)
    assert api.calls == ["impersonate", "read", "revert"]


def test_failed_reversion_requires_process_termination():
    api = FakeApi(reverts=False)
    terminated = []
    with pytest.raises(RuntimeError, match="Fatal"):
        identify_pipe_client(123, api=api, terminate=terminated.append)
    assert terminated == [70]
