"""Durable bounded connection epochs; gaps never establish trading continuity."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from risk.paper_state import PaperStateError


class PaperConnectionJournal:
    def __init__(self, store):
        self.store = store
        self.identifier = str(uuid4())
        with store.transaction() as state:
            epochs = state.setdefault("paper_connection_epochs", {})
            if any(row.get("phase") != "CLOSED" for row in epochs.values()):
                raise PaperStateError("Interrupted connection requires scoped recovery")
            epochs[self.identifier] = {
                "phase": "CONNECTING",
                "started_at_utc": datetime.now(UTC).isoformat(),
                "continuity_verified": False,
                "execution_available": False,
            }

    def connected_after_check(self, report):
        if (
            report.get("account_observed") is not True
            or report.get("execution_available") is not False
            or report.get("trial_started") is not False
        ):
            raise PaperStateError("Fresh read-only checkpoint required")
        with self.store.transaction() as state:
            row = state["paper_connection_epochs"][self.identifier]
            if row["phase"] != "CONNECTING":
                raise PaperStateError("Unexpected connection transition")
            row.update(
                phase="OBSERVING",
                reconciled_after_authentication=True,
                checkpoint_report_sha256=hashlib.sha256(
                    json.dumps(report, sort_keys=True).encode()
                ).hexdigest(),
            )

    def finish(self, *, completed):
        with self.store.transaction() as state:
            row = state["paper_connection_epochs"][self.identifier]
            if row["phase"] not in {"CONNECTING", "OBSERVING"}:
                raise PaperStateError("Connection already closed or failed")
            if completed and row["phase"] != "OBSERVING":
                raise PaperStateError("Connection checkpoint missing")
            row.update(
                phase="CLOSED" if completed else "FAILED",
                finished_at_utc=datetime.now(UTC).isoformat(),
            )
            # Ending even a successful bounded window does not qualify ongoing continuity.
            state["latch_reasons"] = sorted(
                set(state["latch_reasons"]) | {"PAPER_CONNECTION_CONTINUITY_UNQUALIFIED"}
            )
