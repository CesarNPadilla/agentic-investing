"""Isolated PostgreSQL synthetic risk/latch/reservation transaction foundation."""
import hashlib
import re
from decimal import Decimal, DecimalException
from typing import Literal

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict

from risk.evidence_v11 import (
    SyntheticEvidence,
    SyntheticReviewBinding,
    check_synthetic_evidence,
)
from risk.loss_accounting_v11 import (
    LossAccountingDiagnostic,
    SyntheticLossEvidence,
    calculate_synthetic_loss,
)
from risk.reservations_v11 import Nonnegative
from risk.sleeve_v11 import SleeveDiagnostic, SyntheticSleeveInput, evaluate_synthetic_sleeve


class AtomicSyntheticResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    diagnostic: SleeveDiagnostic
    reservation_present: bool
    committed: Nonnegative
    latched: bool
    execution_available: Literal[False] = False


class PostgresSyntheticError(RuntimeError):
    """Unavailable, invalid or conflicting state must block; no fallback."""


class PostgresSyntheticScope:
    """One synthetic account/sleeve; fixed budgets and conservative cost exposure.

    Uses SERIALIZABLE plus an aggregate row lock, retrying serialization/deadlock
    failures with fresh state. Filled and pending costs stay committed until
    verified synthetic terminal evidence releases the unfilled amount. Cost is
    not a live mark: this adapter is never a production risk/execution boundary.
    """
    def __init__(self, dsn: str, schema: str):
        if not re.fullmatch(r"synthetic_v11d_[0-9a-f]{32}", schema):
            raise PostgresSyntheticError("Explicit isolated synthetic schema required")
        self.schema_name = schema
        self._dsn = dsn
        self._table = sql.Identifier(schema, "scope")
        self._schema = sql.Identifier(schema)

    def initialize(self, *, cash: Decimal, sleeve: Decimal, initial_latched: bool = True):
        if type(initial_latched) is not bool:
            raise PostgresSyntheticError("Explicit boolean latch required")
        cash, sleeve = Decimal(cash), Decimal(sleeve)
        if not cash.is_finite() or not sleeve.is_finite() or cash < 0 or not 0 <= sleeve <= 1000:
            raise PostgresSyntheticError("Invalid synthetic budgets")
        state = {"version": "synthetic-v11d", "cash": str(cash), "sleeve": str(sleeve),
                     "latched": initial_latched, "orders": {}, "events": []}
        try:
            with psycopg.connect(self._dsn) as db:
                db.execute(sql.SQL("CREATE SCHEMA {}").format(self._schema))
                db.execute(sql.SQL("CREATE TABLE {} (id integer PRIMARY KEY CHECK (id=1), "
                                   "state jsonb NOT NULL)").format(self._table))
                db.execute(sql.SQL("INSERT INTO {} VALUES (1, %s)").format(self._table), (Jsonb(state),))
        except psycopg.Error:
            raise PostgresSyntheticError("Synthetic initialization failed; existing state is never replaced") from None

    @staticmethod
    def _verify(state):
        if state["version"] != "synthetic-v11d" or type(state["latched"]) is not bool:
            raise PostgresSyntheticError("Invalid persisted synthetic state")
        cash, sleeve = Decimal(state["cash"]), Decimal(state["sleeve"])
        if not cash.is_finite() or not sleeve.is_finite() or cash < 0 or not 0 <= sleeve <= 1000:
            raise PostgresSyntheticError("Invalid persisted capacities")
        used = Decimal(0)
        for order in state["orders"].values():
            amount, filled = Decimal(order["amount"]), Decimal(order["filled"])
            if (not amount.is_finite() or not filled.is_finite() or amount <= 0
                    or not 0 <= filled <= amount or type(order["terminal"]) is not bool):
                raise PostgresSyntheticError("Invalid persisted reservation")
            used += filled if order["terminal"] else amount
        if used > min(cash, sleeve):
            raise PostgresSyntheticError("Persisted budget exceeded")
        if state.get("loss_accounting"):
            record = state["loss_accounting"]
            evidence = SyntheticLossEvidence.model_validate_json(record["evidence"])
            diagnostic = LossAccountingDiagnostic.model_validate_json(record["diagnostic"])
            from datetime import datetime
            if calculate_synthetic_loss(evidence, now=datetime.fromisoformat(record["evaluated_at"])) != diagnostic:
                raise PostgresSyntheticError("Loss accounting replay mismatch")
            if diagnostic.persistent_latch_required and not state["latched"]:
                raise PostgresSyntheticError("Loss latch cannot be cleared")
        return cash, sleeve, used

    def _transaction(self, operation):
        for _ in range(5):
            try:
                with psycopg.connect(self._dsn) as db:
                    db.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                    row = db.execute(sql.SQL("SELECT state FROM {} WHERE id=1 FOR UPDATE").format(
                        self._table)).fetchone()
                    if row is None:
                        raise PostgresSyntheticError("Missing persisted scope")
                    state = row[0]
                    self._verify(state)
                    result = operation(state)
                    self._verify(state)
                    db.execute(sql.SQL("UPDATE {} SET state=%s WHERE id=1").format(self._table),
                               (Jsonb(state),))
                # Return only after the transaction commits successfully.
                return result
            except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected):
                continue
            except (psycopg.Error, DecimalException, ValueError, KeyError, TypeError, AttributeError):
                raise PostgresSyntheticError("Synthetic transaction unavailable or inconsistent") from None
        raise PostgresSyntheticError("Synthetic transaction retry budget exhausted")

    def record_loss_accounting(self, evidence: SyntheticLossEvidence, *, now):
        def record(state):
            prior = state.get("loss_accounting")
            if prior:
                old = SyntheticLossEvidence.model_validate_json(prior["evidence"])
                if (old.baseline_id != evidence.baseline_id or old.baseline_at != evidence.baseline_at
                        or old.initial_funded_equity != evidence.initial_funded_equity
                        or evidence.as_of < old.as_of or evidence.daily_baseline_at < old.daily_baseline_at):
                    raise PostgresSyntheticError("Baseline revision or time regression requires separate review")
                if (old.daily_baseline_at == evidence.daily_baseline_at
                        and old.daily_baseline_marked_equity != evidence.daily_baseline_marked_equity):
                    raise PostgresSyntheticError("Daily baseline cannot change silently")
                old_flows = {f.flow_id: f for f in old.flows}
                new_flows = {f.flow_id: f for f in evidence.flows}
                if any(new_flows.get(key) != value for key, value in old_flows.items()):
                    raise PostgresSyntheticError("Previously recorded flows cannot change or disappear")
                if any(f.flow_id not in old_flows and f.posted_at <= old.as_of for f in evidence.flows):
                    raise PostgresSyntheticError("Retroactive flow correction requires separate review")
                if evidence.as_of == old.as_of and evidence != old:
                    raise PostgresSyntheticError("Same-cutoff evidence cannot be rewritten")
            diagnostic = calculate_synthetic_loss(evidence, now=now)
            state["loss_accounting"] = {"evidence": evidence.model_dump_json(),
                                        "diagnostic": diagnostic.model_dump_json(),
                                        "evaluated_at": now.isoformat()}
            state["latched"] = state["latched"] or diagnostic.persistent_latch_required
            state["events"].append({"kind": "LOSS_ACCOUNTING", **state["loss_accounting"]})
            return diagnostic
        return self._transaction(record)

    def assess_and_reserve(self, proposal_id: str, symbol: str, data: SyntheticSleeveInput,
                           *, evidence_bundle: SyntheticEvidence | None = None,
                           review: SyntheticReviewBinding | None = None):
        if not proposal_id or not re.fullmatch(r"[A-Z][A-Z0-9.]{0,9}", symbol):
            raise PostgresSyntheticError("Synthetic proposal identity and symbol required")
        digest = hashlib.sha256((symbol + "\n" + data.model_dump_json()).encode()).hexdigest()
        amount = data.quantity * data.conservative_price + data.estimated_fees

        def assess(state):
            cash, sleeve, used = self._verify(state)
            existing = state["orders"].get(proposal_id)
            if existing and (existing["digest"] != digest or existing["terminal"]):
                raise PostgresSyntheticError("Changed or terminal proposal identity reused")
            # Fixture input commitments must exclude this ledger. Existing own
            # reservation is excluded during exact retry to avoid double count.
            others = {key: order for key, order in state["orders"].items() if key != proposal_id}
            committed = sum((Decimal(o["filled"] if o["terminal"] else o["amount"])
                             for o in others.values()), Decimal(0))
            same = sum((Decimal(o["filled"] if o["terminal"] else o["amount"])
                        for o in others.values() if o["symbol"] == symbol), Decimal(0))
            loss_changes, loss_reasons = {}, ()
            if state.get("loss_accounting"):
                recorded = state["loss_accounting"]
                loss_evidence = SyntheticLossEvidence.model_validate_json(recorded["evidence"])
                loss = calculate_synthetic_loss(loss_evidence, now=data.now)
                if not loss.accounting_available:
                    loss_reasons = ("LOSS_ACCOUNTING_UNAVAILABLE",) + loss.reason_codes
                elif data.snapshot_cutoff != loss_evidence.as_of:
                    loss_reasons = ("LOSS_ACCOUNTING_SNAPSHOT_MISMATCH",)
                else:
                    loss_changes = {
                        "initial_funded_sleeve": loss_evidence.initial_funded_equity,
                        "current_flow_adjusted_equity": loss.current_flow_adjusted_equity,
                        "start_of_day_flow_adjusted_equity": loss.start_of_day_flow_adjusted_equity,
                        "daily_net_pnl": loss.daily_net_pnl,
                        "cumulative_net_pnl": loss.cumulative_net_pnl,
                    }
            effective = SyntheticSleeveInput.model_validate(data.model_dump() | loss_changes | {
                "unreserved_settled_cash": min(data.unreserved_settled_cash, cash-committed),
                "acquisition_commitments": data.acquisition_commitments+committed,
                "same_name_marked_commitments": data.same_name_marked_commitments+same,
                "gross_marked_commitments": data.gross_marked_commitments+committed,
                "kill_switch_latched": state["latched"] or data.kill_switch_latched,
            })
            diagnostic = evaluate_synthetic_sleeve(effective)
            if loss_reasons:
                diagnostic = diagnostic.model_copy(update={"sleeve_checks_passed": False,
                    "reason_codes": diagnostic.reason_codes + loss_reasons})
            if evidence_bundle is not None:
                checked = check_synthetic_evidence(evidence_bundle, now=data.now,
                                                   proposal_digest=digest, review=review)
                evidence_reasons = checked.reason_codes
                if (evidence_bundle.symbol != symbol
                        or evidence_bundle.quote_event_time != data.quote_event_time
                        or evidence_bundle.snapshot_cutoff != data.snapshot_cutoff
                        or evidence_bundle.ask is None
                        or data.conservative_price < evidence_bundle.ask
                        or review is None or review.risk_evaluated_at != data.risk_evaluation_time):
                    evidence_reasons += ("EVIDENCE_RISK_INPUT_MISMATCH",)
                if evidence_reasons:
                    diagnostic = diagnostic.model_copy(update={
                        "sleeve_checks_passed": False,
                        "reason_codes": diagnostic.reason_codes + evidence_reasons,
                    })
            elif review is not None:
                raise PostgresSyntheticError("Review requires matching synthetic evidence")
            if diagnostic.sleeve_checks_passed and used+amount > min(cash, sleeve) and not existing:
                diagnostic = diagnostic.model_copy(update={
                    "sleeve_checks_passed": False,
                    "reason_codes": diagnostic.reason_codes + ("RESERVATION_CAPACITY",),
                })
            state["latched"] = state["latched"] or diagnostic.persistent_latch_required
            if not existing and diagnostic.sleeve_checks_passed and used+amount <= min(cash, sleeve):
                state["orders"][proposal_id] = {"digest": digest, "symbol": symbol, "amount": str(amount),
                                                   "filled": "0", "terminal": False}
            present = proposal_id in state["orders"]
            state["events"].append({"evidence": evidence_bundle.model_dump_json() if evidence_bundle else None,
                                         "review": review.model_dump_json() if review else None,
                                         "kind": "ASSESS", "proposal_id": proposal_id, "digest": digest,
                                         "input": effective.model_dump_json(),
                                         "diagnostic": diagnostic.model_dump_json(),
                                         "reservation_present": present})
            return AtomicSyntheticResult(diagnostic=diagnostic, reservation_present=present,
                                         committed=self._verify(state)[2], latched=state["latched"])
        return self._transaction(assess)

    def reconcile(self, proposal_id: str, *, cumulative_filled: Decimal, status: str,
                  synthetic_terminal_verified: bool = False):
        if status not in {"OPEN", "PARTIAL", "UNKNOWN", "PENDING_CANCEL", "CANCELED", "REJECTED", "FILLED"}:
            raise PostgresSyntheticError("Invalid status")
        if type(synthetic_terminal_verified) is not bool:
            raise PostgresSyntheticError("Explicit synthetic verification required")
        def update(state):
            order = state["orders"].get(proposal_id)
            filled = Decimal(cumulative_filled)
            if (not order or not filled.is_finite() or filled < Decimal(order["filled"])
                    or filled > Decimal(order["amount"])):
                raise PostgresSyntheticError("Invalid cumulative fill")
            terminal = synthetic_terminal_verified and status in {"CANCELED", "REJECTED", "FILLED"}
            if order["terminal"] and (not terminal or filled != Decimal(order["filled"])):
                raise PostgresSyntheticError("Terminal reservation cannot reopen")
            order.update(filled=str(filled), terminal=terminal)
            state["events"].append({"kind": "RECONCILE", "proposal_id": proposal_id,
                                         "filled": str(filled), "status": status, "verified": synthetic_terminal_verified})
            return {"committed": str(self._verify(state)[2]), "latched": state["latched"], "execution_available": False}
        return self._transaction(update)

    def snapshot(self):
        return self._transaction(lambda state: {"committed": str(self._verify(state)[2]),
                                                    "latched": state["latched"],
                                                    "order_count": len(state["orders"]),
                                                    "event_count": len(state["events"]), "execution_available": False})
