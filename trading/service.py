"""Transactional synthetic broker. No network path or live broker credentials.

All mutations acquire the same database row lock via UPDATE, serializing risk,
approval, execution, and the kill switch across processes. Synthetic fills and
audit events commit atomically; a real adapter needs an outbox and reconciliation.
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import JSON, Integer, String, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from database.repository import Base, SimulationRow
from integrations.brokers.execution import SyntheticExecutionBroker
from risk.trading import evaluate_trade
from simulation.models import SimulationRun
from trading.automation import qualify_strategy
from trading.models import AutomationPolicyInput, ProposalInput


class ControlRow(Base):
    __tablename__ = "trading_control"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)


class ProposalRow(Base):
    __tablename__ = "trade_proposals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(100), unique=True)
    payload: Mapped[dict] = mapped_column(JSON)


class AuditRow(Base):
    __tablename__ = "trading_audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class TradeConflict(ValueError):
    pass


class TradingService:
    def __init__(self, engine):
        self.engine = engine

    def initialize(self):
        # Called once at startup; unique PK prevents competing initializations
        # from overwriting an existing kill switch or account.
        from sqlalchemy.exc import IntegrityError

        try:
            with Session(self.engine) as session, session.begin():
                if session.get(ControlRow, 1) is None:
                    session.add(
                        ControlRow(
                            id=1,
                            revision=0,
                            payload={
                                "killed": True,
                                "cash": "10000",
                                "positions": {},
                            },
                        )
                    )
        except IntegrityError:
            with Session(self.engine) as session:
                if session.get(ControlRow, 1) is None:
                    raise

    def register_automation_policy(self, inputs: AutomationPolicyInput):
        now = datetime.now(UTC)
        policy = {
            "policy": inputs.model_dump(mode="json"),
            "registered_at": now.isoformat(),
            "qualification": None,
        }
        with Session(self.engine) as session, session.begin():
            control = self._lock(session)
            control.payload = {**control.payload, "automation": policy}
            self._audit(session, "automation_policy_registered", "human", policy=policy)
        return self.automation_status()

    def qualify_automation(self, backtest_id, paper_run_id):
        with Session(self.engine) as session, session.begin():
            control = self._lock(session)
            registered = control.payload.get("automation")
            if registered is None:
                raise TradeConflict("Register an automation policy before evaluating evidence")
            backtest_row = session.get(SimulationRow, str(backtest_id))
            paper_row = session.get(SimulationRow, str(paper_run_id))
            if backtest_row is None or paper_row is None:
                raise KeyError(backtest_id if backtest_row is None else paper_run_id)
            backtest = SimulationRun.model_validate(backtest_row.payload)
            paper = SimulationRun.model_validate(paper_row.payload)
            result = qualify_strategy(
                AutomationPolicyInput.model_validate(registered["policy"]),
                datetime.fromisoformat(registered["registered_at"]),
                backtest,
                paper,
            )
            qualification = {
                **result,
                "backtest_id": str(backtest_id),
                "paper_run_id": str(paper_run_id),
                "checked_at": datetime.now(UTC).isoformat(),
            }
            control.payload = {
                **control.payload,
                "automation": {**registered, "qualification": qualification},
            }
            self._audit(
                session,
                "automation_qualified" if result["passed"] else "automation_rejected",
                "human",
                qualification=qualification,
            )
        return self.automation_status()

    def automation_status(self):
        with Session(self.engine) as session:
            control = session.get(ControlRow, 1)
            automation = control.payload.get("automation") if control else None
            qualification = automation.get("qualification") if automation else None
            return {
                "execution_enabled": False,
                "execution_available": False,
                "kill_switch_enabled": control.payload["killed"] if control else True,
                "policy": automation,
                "qualified": bool(qualification and qualification["passed"]),
                "unmet_execution_controls": [
                    "No automated order-submission path is enabled",
                    "Trusted regular-session enforcement is not wired",
                    "Mark-to-market portfolio exposure and daily-loss checks are not wired",
                    "No live execution adapter or strategy scheduler is configured",
                ],
            }

    def _lock(self, session):
        result = session.execute(
            update(ControlRow).where(ControlRow.id == 1).values(revision=ControlRow.revision + 1)
        )
        if result.rowcount != 1:
            raise TradeConflict("Trading control unavailable")
        return session.get(ControlRow, 1)

    def _audit(self, session, event, actor, proposal_id=None, **details):
        session.add(
            AuditRow(
                id=str(uuid4()),
                payload={
                    "at": datetime.now(UTC).isoformat(),
                    "event": event,
                    "actor": actor,
                    "proposal_id": proposal_id,
                    **details,
                },
            )
        )

    def propose(self, inputs: ProposalInput):
        order = inputs.model_dump(mode="json")
        with Session(self.engine) as session, session.begin():
            control = self._lock(session)
            existing = session.query(ProposalRow).filter_by(request_id=inputs.request_id).first()
            if existing:
                if existing.payload["order"] != order:
                    raise TradeConflict("Request ID already used for different proposal")
                return existing.payload
            now = datetime.now(UTC)
            payload = {
                "id": str(uuid4()),
                "order": order,
                "broker": "synthetic",
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(minutes=15)).isoformat(),
            }
            payload["digest"] = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            payload["risk"] = evaluate_trade(order, control.payload)
            payload["status"] = "pending_approval" if payload["risk"]["passed"] else "blocked"
            session.add(
                ProposalRow(id=payload["id"], request_id=inputs.request_id, payload=payload)
            )
            self._audit(
                session,
                "proposed",
                "agent",
                payload["id"],
                risk=payload["risk"],
                digest=payload["digest"],
            )
            return payload

    def get(self, proposal_id):
        with Session(self.engine) as session:
            row = session.get(ProposalRow, str(proposal_id))
            return row.payload if row else None

    def transition(self, proposal_id, action, digest=None):
        with Session(self.engine) as session, session.begin():
            control = self._lock(session)
            row = session.get(ProposalRow, str(proposal_id))
            if row is None:
                raise KeyError(proposal_id)
            payload = dict(row.payload)
            if action == "approve" and digest != payload["digest"]:
                raise TradeConflict("Approval digest does not match immutable proposal")
            if action == "approve" and payload["status"] in {"approved", "filled"}:
                return payload
            if action == "execute" and payload["status"] == "filled":
                return payload
            expected = "approved" if action == "execute" else "pending_approval"
            if payload["status"] != expected:
                raise TradeConflict(f"Requires {expected} state")
            actor = "executor" if action == "execute" else "human"
            if action == "reject":
                payload["status"] = "rejected"
            elif datetime.fromisoformat(payload["expires_at"]) <= datetime.now(UTC):
                payload["status"] = "expired"
            else:
                payload["risk"] = evaluate_trade(payload["order"], control.payload)
                if not payload["risk"]["passed"]:
                    payload["status"] = "blocked"
                elif action == "approve":
                    payload["status"] = "approved"
                    payload["approval"] = {
                        "actor": "human",
                        "digest": digest,
                        "at": datetime.now(UTC).isoformat(),
                    }
                else:
                    account, receipt = SyntheticExecutionBroker.fill(
                        payload["id"], payload["order"], control.payload
                    )
                    control.payload = account
                    payload["status"] = "filled"
                    payload["broker_order"] = receipt
            row.payload = payload
            self._audit(
                session,
                payload["status"],
                actor,
                str(proposal_id),
                digest=payload["digest"],
                risk=payload["risk"],
            )
            return payload

    def kill(self, enabled):
        with Session(self.engine) as session, session.begin():
            control = self._lock(session)
            control.payload = {**control.payload, "killed": enabled}
            self._audit(session, "kill_switch", "human", enabled=enabled)
            return {"enabled": enabled}

    def account(self):
        with Session(self.engine) as session:
            return {
                "broker": "synthetic",
                "account_id": "synthetic-phase4",
                **session.get(ControlRow, 1).payload,
            }

    def audit(self):
        with Session(self.engine) as session:
            return sorted([row.payload for row in session.query(AuditRow)], key=lambda x: x["at"])

    def reconcile(self):
        """Check the synthetic ledger against persisted fills under a consistent lock."""
        with Session(self.engine) as session, session.begin():
            control = self._lock(session)
            cash, positions, issues = Decimal(10000), {}, []
            count = 0
            for row in session.query(ProposalRow):
                proposal = row.payload
                if proposal["status"] != "filled":
                    continue
                count += 1
                order, receipt = proposal["order"], proposal["broker_order"]
                if (
                    receipt["client_order_id"] != row.id
                    or proposal.get("approval", {}).get("digest") != proposal["digest"]
                    or Decimal(receipt["filled_quantity"]) != Decimal(order["quantity"])
                    or Decimal(receipt["fill_price"]) != Decimal(order["limit_price"])
                ):
                    issues.append(f"Receipt/approval mismatch: {row.id}")
                delta = Decimal(receipt["filled_quantity"])
                if order["side"] == "sell":
                    delta = -delta
                cash -= delta * Decimal(receipt["fill_price"])
                positions[order["symbol"]] = positions.get(order["symbol"], Decimal(0)) + delta
            actual = {symbol: Decimal(qty) for symbol, qty in control.payload["positions"].items()}
            if cash != Decimal(control.payload["cash"]) or positions != actual:
                issues.append("Account ledger does not match synthetic receipts")
            if issues:
                control.payload = {**control.payload, "killed": True}
            result = {
                "broker": "synthetic",
                "matched": not issues,
                "fills_checked": count,
                "issues": issues,
            }
            self._audit(session, "reconciled", "human", **result)
            return result
