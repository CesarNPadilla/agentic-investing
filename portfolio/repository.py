"""Local append-only research evidence store, independent of trading tables/routes."""

import sqlite3
from datetime import datetime
from pathlib import Path

from portfolio.reconciliation import reconcile
from portfolio.state import PortfolioState, Reconciliation, Record
from risk.evaluator import HypotheticalTrade, KillSwitch, RiskEvaluation, digest, evaluate
from risk.policy import InvestmentPolicy


class EvaluationEvidence(Record):
    policy: InvestmentPolicy
    opening: PortfolioState
    closing: PortfolioState
    proposal: HypotheticalTrade
    kill_switch: KillSwitch
    reconciliation: Reconciliation
    evaluation: RiskEvaluation


class PortfolioRepository:
    """SQLite file for local research only; no network calls or broker credentials.

    Inputs, transaction history, reconciliation and decision commit in one row.
    Content-addressed inserts make identical retries idempotent, not updates.
    """

    def __init__(self, path: Path):
        self.path = path
        with sqlite3.connect(path) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS portfolio_evidence_v4 (
                id TEXT PRIMARY KEY, checksum TEXT NOT NULL, payload TEXT NOT NULL
            )""")

    def evaluate_and_record(
        self,
        policy: InvestmentPolicy,
        opening: PortfolioState,
        closing: PortfolioState,
        proposal: HypotheticalTrade,
        kill_switch: KillSwitch,
        *,
        now: datetime,
    ) -> EvaluationEvidence:
        decision = evaluate(policy, opening, closing, proposal, kill_switch, now=now)
        evidence = EvaluationEvidence(
            policy=policy,
            opening=opening,
            closing=closing,
            proposal=proposal,
            kill_switch=kill_switch,
            reconciliation=reconcile(opening, closing),
            evaluation=decision,
        )
        payload = evidence.model_dump_json()
        checksum = digest(evidence)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO portfolio_evidence_v4 VALUES (?, ?, ?)",
                (decision.input_digest, checksum, payload),
            )
            row = connection.execute(
                "SELECT checksum FROM portfolio_evidence_v4 WHERE id = ?", (decision.input_digest,)
            ).fetchone()
            if row[0] != checksum:
                raise ValueError("Conflicting evidence for identical inputs")
        # Storage errors propagate; never report successful persistence on failure.
        return evidence

    def get(self, evidence_id: str) -> EvaluationEvidence | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                "SELECT checksum, payload FROM portfolio_evidence_v4 WHERE id = ?", (evidence_id,)
            ).fetchone()
        if row is None:
            return None
        evidence = EvaluationEvidence.model_validate_json(row[1])
        if digest(evidence) != row[0]:
            raise ValueError("Evidence checksum mismatch")
        return evidence
