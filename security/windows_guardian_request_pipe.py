"""Staged single-use guardian transport; no deployment, service or reset authority."""

from datetime import UTC, datetime

from security.webull_guardian_bridge import dispatch_guardian_connected
from security.windows_local_request_pipe import LocalRequestPipe


class GuardianRequestPipe(LocalRequestPipe):
    def __init__(self, *, guardian_sid, owner_sid):
        # Base transport's names describe server/client roles. The guardian is
        # the server here; its role-specific dispatch does not register runtime requests.
        super().__init__(owner_sid=guardian_sid, runtime_sid=owner_sid)

    def _dispatch(self, raw, reference):
        return dispatch_guardian_connected(
            self.handle,
            raw,
            reference,
            guardian_sid=self.owner_sid,
            owner_sid=self.runtime_sid,
            now=datetime.now(UTC),
            identity_api=self.api,
        )
