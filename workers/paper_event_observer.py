"""Read-only event/timer callbacks into durable, deadline-bounded paper diagnostics."""

import hashlib
import json
import time
from datetime import UTC, datetime
from uuid import UUID, uuid4

from risk.paper_state import PaperStateError
from workers.paper_observation_deadline import bounded_observation

EVENTS = {
    "new",
    "fill",
    "partial_fill",
    "canceled",
    "expired",
    "done_for_day",
    "replaced",
    "accepted",
    "rejected",
    "pending_new",
    "stopped",
    "pending_cancel",
    "pending_replace",
    "calculated",
    "suspended",
    "order_replace_rejected",
    "order_cancel_rejected",
}


class PaperEventObserver:
    def __init__(
        self,
        store,
        cycle,
        *,
        account_binding,
        timeout_seconds=5,
        monotonic=time.monotonic,
        symbol="INTC",
        recovery_credential=None,
    ):
        if symbol not in {"SCHB", "INTC"}:
            raise PaperStateError("Unsupported diagnostic security")
        self.symbol = symbol
        state = store.read()
        if state["binding"] != account_binding:
            raise PaperStateError("Event observer account changed")
        if {"OBSERVER_DEADLINE_MISSED", "ACTIVE_SCOPE_MONITORING_DEADLINE_MISSED"} & set(
            state["latch_reasons"]
        ):
            raise PaperStateError("Event observer requires service recovery")
        acknowledged = set()
        if state.get("paper_readonly_recoveries"):
            if recovery_credential is None:
                raise PaperStateError("Recovery credential required")
            from security.paper_observer_recovery import acknowledged_failure_ids

            try:
                acknowledged = acknowledged_failure_ids(state, recovery_credential)
            except (ValueError, TypeError, KeyError):
                raise PaperStateError("Recovery acknowledgement invalid") from None
        if any(
            row.get("completed") is not True and identifier not in acknowledged
            for identifier, row in state.get("paper_event_checks", {}).items()
        ):
            raise PaperStateError("Incomplete event journal requires recovery")
        self.store, self.cycle = store, cycle
        self.timeout_seconds = timeout_seconds
        self.epoch = str(uuid4())
        self.stopped = False
        self.reports = []
        self.monotonic = monotonic
        self.last_completed = None
        self.active_scope = False

    def check(self, trigger, digest=None):
        if self.stopped:
            raise PaperStateError("Event observer stopped")
        remaining = self.timeout_seconds
        if self.active_scope and self.last_completed is not None:
            elapsed = self.monotonic() - self.last_completed
            if elapsed < 0 or elapsed >= 5:
                self.stopped = True
                self.store.latch("ACTIVE_SCOPE_MONITORING_DEADLINE_MISSED")
                raise PaperStateError("Active scope deadline missed")
            remaining = min(remaining, 5 - elapsed)
        identifier = str(uuid4())
        with self.store.transaction() as state:
            state.setdefault("paper_event_checks", {})[identifier] = {
                "epoch": self.epoch,
                "trigger": trigger,
                "event_digest": digest,
                "started_at": datetime.now(UTC).isoformat(),
                "completed": False,
            }
        try:
            if self.active_scope and self.last_completed is not None:
                elapsed = self.monotonic() - self.last_completed
                if elapsed < 0 or elapsed >= 5:
                    self.store.latch("ACTIVE_SCOPE_MONITORING_DEADLINE_MISSED")
                    raise PaperStateError("Active scope deadline missed during journal write")
                remaining = min(remaining, 5 - elapsed)
            report = bounded_observation(
                self.cycle, timeout_seconds=remaining, on_timeout=self.store.latch
            )
            if report.get("execution_available") is not False:
                raise PaperStateError("Unrecognized observer admission state")
            successful_read = (
                "OBSERVER_DEADLINE_MISSED" not in report["blockers"]
                and report.get("account_observed") is True
            )
            with self.store.transaction() as state:
                state["paper_event_checks"][identifier].update(
                    completed=successful_read,
                    completed_at=datetime.now(UTC).isoformat(),
                    blockers=report["blockers"],
                )
            self.reports.append(report)
            if not successful_read:
                raise PaperStateError("Event observer source or deadline failed")
            self.last_completed = self.monotonic()
            self.active_scope = bool(report.get("active_scope"))
            return report
        except (RuntimeError, ValueError, TypeError, OSError):
            self.stopped = True
            self.store.latch("PAPER_EVENT_OBSERVER_FAILED")
            raise PaperStateError("Event observer stopped after diagnostic failure") from None

    def on_event(self, payload):
        try:
            if not isinstance(payload, dict) or payload.get("event") not in EVENTS:
                raise ValueError("Unknown event")
            order = payload["order"]
            UUID(order["id"])
            if order["symbol"] != self.symbol:
                raise ValueError("Unexpected security")
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        except (ValueError, TypeError, KeyError):
            self.stopped = True
            self.store.latch("PAPER_EVENT_UNQUALIFIED")
            raise PaperStateError("Unqualified paper event") from None
        return self.check(
            "FILL" if payload["event"] in {"fill", "partial_fill"} else "ORDER", digest
        )

    def on_timer(self):
        return self.check("TIMER")
