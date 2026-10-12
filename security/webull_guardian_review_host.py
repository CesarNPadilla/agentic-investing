"""Staged two-request review host; no service, reset or broker entry point."""

import hashlib
from datetime import UTC, datetime

from security.webull_guardian_recovery_inspection import inspect_guardian_review
from security.webull_guardian_reference import parse_guardian_request
from security.windows_guardian_exchange_pipe import GuardianExchangePipe


class GuardianReviewHost:
    """Provisioning/configuration and OS identity must be independently qualified.

    A protected provisioned context digest is supplied by deployment code, never
    the request. The exclusive start marker prevents reusing this host directory
    after interruption. No startup/recovery path deletes or repairs evidence.
    """

    def __init__(
        self,
        reference,
        *,
        guardian_sid,
        owner_sid,
        provisioned_envelope_sha256,
        now=None,
        pipe_factory=None,
    ):
        if provisioned_envelope_sha256 != reference.journal.expected_envelope.digest():
            raise ValueError("Provisioned review context mismatch")
        self.reference = reference
        self.guardian_sid, self.owner_sid = guardian_sid, owner_sid
        self.now = now or (lambda: datetime.now(UTC))
        self.pipe_factory = pipe_factory or (
            lambda: GuardianExchangePipe(guardian_sid=guardian_sid, owner_sid=owner_sid)
        )
        self.started = reference.directory / "host-start.json"
        self.terminal = reference.directory / "host-terminal.json"
        self.used = False

    def run(self, publish, *, stop_requested=lambda: False):
        if self.used:
            raise ValueError("Single-use review host already used")
        self.used = True
        before = inspect_guardian_review(self.reference, now=self.now())
        if (
            before["reference_state"] != "NO_RETAINED_EVIDENCE_FRESHNESS_UNESTABLISHED"
            or self.terminal.exists()
        ):
            raise ValueError("Retained state requires separate reconciliation; host blocked")
        # Exclusive creation is the admission boundary for concurrent host starts.
        self.reference._exclusive(
            self.started,
            {
                "schema_version": "webull-review-host-start-v1",
                "envelope_sha256": self.reference.journal.expected_envelope.digest(),
                "started_at": self.now().isoformat(),
                "reset_authorized": False,
                "execution_available": False,
            },
        )
        expected = ["PREPARE_REVIEW_REFERENCE", "CONFIRM_REVIEW_CONSUMPTION"]
        completed = []
        pipe = None

        class OrderedReference:
            def __init__(self, reference, expected_action):
                self.reference, self.expected_action = reference, expected_action

            def handle(self, raw, *, now):
                request = parse_guardian_request(
                    raw, self.reference.journal.expected_envelope.digest()
                )
                if request["action"] != self.expected_action:
                    raise ValueError("Review host request out of order")
                return self.reference.handle(raw, now=now)

        try:
            for action in expected:
                if stop_requested():
                    raise InterruptedError("Review host stop requested")
                pipe = self.pipe_factory()
                publish(
                    {
                        "schema_version": "webull-review-host-ready-v1",
                        "pipe_name": pipe.name,
                        "action": action,
                        "envelope_sha256": self.reference.journal.expected_envelope.digest(),
                    }
                )
                pipe.register_one(OrderedReference(self.reference, action), timeout_seconds=5)
                pipe.close()
                pipe = None
                completed.append(action)
            if stop_requested():
                raise InterruptedError("Review host stop requested")
            result = inspect_guardian_review(self.reference, now=self.now())
            if result["reference_state"] != "MATCHING_RETAINED_REVIEW_NO_RESET_AUTHORITY":
                raise ValueError("Review host terminal evidence mismatch")
            state = "REVIEW_RETAINED_HOST_CLOSED_NO_RESET_AUTHORITY"
        except BaseException:
            self.reference._exclusive(
                self.terminal,
                {
                    "schema_version": "webull-review-host-terminal-v1",
                    "state": "BLOCKED_RECONCILIATION_REQUIRED",
                    "completed_actions": completed,
                    "observed_at": self.now().isoformat(),
                    "reset_authorized": False,
                    "execution_available": False,
                },
            )
            raise
        finally:
            if pipe is not None:
                pipe.close()
        record = {
            "schema_version": "webull-review-host-terminal-v1",
            "state": state,
            "completed_actions": completed,
            "observed_at": self.now().isoformat(),
            "start_sha256": hashlib.sha256(self.started.read_bytes()).hexdigest(),
            "reset_authorized": False,
            "execution_available": False,
        }
        self.reference._exclusive(self.terminal, record)
        return record
