"""Staged bounded guardian reply transport; no service or admission authority."""

import ctypes
import json
import time
from ctypes import wintypes

from security.windows_guardian_request_pipe import GuardianRequestPipe


class GuardianExchangePipe(GuardianRequestPipe):
    """Return a framed acknowledgement, then require receipt acknowledgement.

    A client receipt byte prevents DisconnectNamedPipe discarding unread data.
    All operations share the original deadline. No blocking FlushFileBuffers.
    Persisted reference state is preserved when delivery fails.
    """

    def register_one(self, reference, *, timeout_seconds=5):
        self.response_deadline = time.monotonic() + timeout_seconds
        return super().register_one(reference, timeout_seconds=timeout_seconds)

    def _dispatch(self, raw, reference):
        result = super()._dispatch(raw, reference)
        payload = json.dumps(
            result, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        if not 1 <= len(payload) <= 4096:
            raise ValueError("Guardian reply frame exceeds allowed size")
        write = self.api.kernel.WriteFile
        write.argtypes = self.api.kernel.ReadFile.argtypes
        write.restype = wintypes.BOOL
        frame = len(payload).to_bytes(4, "big") + payload
        offset = 0
        while offset < len(frame):
            buffer = ctypes.create_string_buffer(frame[offset:])
            remaining = len(frame) - offset
            count = self._operation(
                lambda op, count, buffer=buffer, remaining=remaining: write(
                    self.handle,
                    buffer,
                    remaining,
                    ctypes.byref(count),
                    ctypes.byref(op),
                ),
                self.response_deadline,
            )
            if not 0 < count <= len(frame) - offset:
                raise OSError("Guardian reply write failed")
            offset += count
        if self._read_exact(1, self.response_deadline) != b"\x01":
            raise ValueError("Guardian reply receipt acknowledgement missing")
        return result
