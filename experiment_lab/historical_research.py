"""Counterfactual historical signals, never TradeProposals or executable fills.

This ledger has no connection to the broker, the InvestmentPolicy risk evaluator,
or the paper clock. Policy-approved backtests remain in backtesting.engine.
"""

from decimal import ROUND_FLOOR, Decimal
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from backtesting.models import Period, ValidationGates
from experiment_lab.definitions import LONG_TERM_ID, SWING_ID
from experiment_lab.historical_data import HistoricalResearchDataset
from experiment_lab.knowledge_boundary import HistoricalKnowledgeBoundary, KnowledgeObservation
from portfolio.state import Record
from risk.evaluator import digest

ZERO = Decimal(0)


class ResearchRules(Record):
    label: Literal["RESEARCH_ONLY_NOT_POLICY_AUTHORIZATION"] = (
        "RESEARCH_ONLY_NOT_POLICY_AUTHORIZATION"
    )
    # Fixed, inspectable exploratory thresholds; changes require a new plan ID.
    growth_minimum: Decimal = Decimal("0.08")
    free_cash_flow_minimum: Decimal = Decimal(0)
    net_debt_to_ebitda_maximum: Decimal = Decimal(3)
    free_cash_flow_yield_minimum: Decimal = Decimal("0.02")
    fundamental_max_age_days: int = Field(default=180, ge=1)
    long_trend_sessions: int = Field(default=200, ge=2)
    long_review_sessions: int = Field(default=21, ge=1)
    swing_fast_sessions: int = Field(default=50, ge=2)
    swing_slow_sessions: int = Field(default=200, ge=3)
    swing_rsi_sessions: int = Field(default=14, ge=2)
    swing_rsi_lower: Decimal = Decimal(50)
    swing_rsi_upper: Decimal = Decimal(75)
    swing_volume_sessions: int = Field(default=20, ge=2)
    swing_atr_sessions: int = Field(default=14, ge=2)
    swing_stop_atr_multiple: Decimal = Field(default=Decimal(2), gt=0)
    swing_max_holding_sessions: int = Field(default=20, ge=1)
    notional_fraction: Decimal = Field(default=Decimal("0.1"), gt=0, le=1)
    commission: Decimal = Field(default=Decimal("0.10"), ge=0)
    slippage_bps: Decimal = Field(default=Decimal(5), ge=0)
    spread_bps: Decimal = Field(default=Decimal(2), ge=0)

    @model_validator(mode="after")
    def coherent(self):
        if self.swing_fast_sessions >= self.swing_slow_sessions:
            raise ValueError("Fast average must be shorter than slow")
        if not ZERO <= self.swing_rsi_lower < self.swing_rsi_upper <= 100:
            raise ValueError("Invalid RSI window")
        return self


class HistoricalResearchPlan(Record):
    plan_id: str
    created_at: AwareDatetime
    dataset_digest: str
    symbols: tuple[str, ...]
    benchmark: Literal["VOO"] = "VOO"
    periods: tuple[Period, Period, Period]
    rules: ResearchRules = ResearchRules()
    gates: ValidationGates
    research_capital: Decimal = Field(default=Decimal(100000), gt=0)
    experimental_capital: Literal[160] = 160
    source_version: str

    @model_validator(mode="after")
    def frozen(self):
        if tuple(p.role for p in self.periods) != (
            "development", "validation", "out_of_sample"
        ) or any(a.end >= b.start for a, b in zip(self.periods, self.periods[1:])):
            raise ValueError("Ordered, non-overlapping development/validation/OOS required")
        if len(set(self.symbols)) != len(self.symbols) or "VOO" in self.symbols:
            raise ValueError("Duplicate symbols or benchmark in strategy universe")
        required = (
            self.gates.minimum_observations,
            self.gates.minimum_trades,
            self.gates.max_drawdown,
            self.gates.max_turnover,
            self.gates.acceptable_data_quality,
        )
        if any(value is None for value in required):
            raise ValueError("All historical validation gates must be frozen")
        if not self.gates.zero_lookahead_violations or not self.gates.zero_policy_bypasses:
            raise ValueError("Zero lookahead and policy bypass gates required")
        return self


def _mean(values):
    return sum(values, ZERO) / len(values)


def _rsi(closes, period):
    changes = [b - a for a, b in zip(closes[-period - 1:-1], closes[-period:])]
    gains = sum((max(c, ZERO) for c in changes), ZERO)
    losses = sum((max(-c, ZERO) for c in changes), ZERO)
    return Decimal(50) if not gains and not losses else Decimal(100) if not losses else (
        100 - 100 / (1 + gains / losses)
    )


def _atr(bars, period):
    pairs = zip(bars[-period - 1:-1], bars[-period:])
    return _mean([
        max(b.high - b.low, abs(b.high - a.close), abs(b.low - a.close))
        for a, b in pairs
    ])


def _fundamentals(dataset, symbol, cutoff, max_age_days, boundary):
    names = ("revenue_growth", "free_cash_flow", "net_debt_to_ebitda", "free_cash_flow_yield")
    latest = {}
    for point in dataset.fundamentals:
        if point.symbol != symbol:
            continue
        if not boundary.require(KnowledgeObservation(
            "fundamental", point.source_id, point.available_at, point.revision_proven,
        ), cutoff):
            continue
        if point.metric in names and (
            point.metric not in latest or
            (point.period_end, point.available_at) >
            (latest[point.metric].period_end, latest[point.metric].available_at)
        ):
            latest[point.metric] = point
    if set(latest) != set(names) or any(
        (cutoff - point.available_at).days > max_age_days for point in latest.values()
    ):
        return None
    return latest


def _signal(strategy, history, dataset, symbol, cutoff, rules, held, held_sessions, stop,
            boundary):
    closes = [b.close for b in history]
    minimum = max(rules.long_trend_sessions, rules.swing_slow_sessions) + 1
    if len(history) < minimum:
        return None, "INSUFFICIENT_WARMUP", None
    price = closes[-1]
    if strategy == LONG_TERM_ID:
        fundamentals = _fundamentals(dataset, symbol, cutoff, rules.fundamental_max_age_days,
                                      boundary)
        if fundamentals is None:
            return None, "MISSING_POINT_IN_TIME_FUNDAMENTALS", None
        values = {name: p.value for name, p in fundamentals.items()}
        qualified = (
            values["revenue_growth"] >= rules.growth_minimum
            and values["free_cash_flow"] > rules.free_cash_flow_minimum
            and values["net_debt_to_ebitda"] <= rules.net_debt_to_ebitda_maximum
            and values["free_cash_flow_yield"] >= rules.free_cash_flow_yield_minimum
        )
        if held and not qualified:
            return "sell", "FUNDAMENTAL_DETERIORATION", None
        if not held and qualified and price > _mean(closes[-rules.long_trend_sessions:]):
            return "buy", "QUALITY_GROWTH_PROXY", None
        return None, "NO_SIGNAL", None
    fast = _mean(closes[-rules.swing_fast_sessions:])
    slow = _mean(closes[-rules.swing_slow_sessions:])
    rsi = _rsi(closes, rules.swing_rsi_sessions)
    atr = _atr(history, rules.swing_atr_sessions)
    prior_volume = _mean([b.volume for b in history[-rules.swing_volume_sessions - 1:-1]])
    if held:
        if price <= stop:
            return "sell", "ATR_STOP", None
        if price < fast or fast < slow:
            return "sell", "TREND_FAILURE", None
        if held_sessions >= rules.swing_max_holding_sessions:
            return "sell", "HOLDING_LIMIT", None
    elif price > slow and fast > slow and rules.swing_rsi_lower < rsi < rules.swing_rsi_upper and history[-1].volume > prior_volume:
        return "buy", "TREND_MOMENTUM", price - rules.swing_stop_atr_multiple * atr
    return None, "NO_SIGNAL", None


def simulate(dataset: HistoricalResearchDataset, plan: HistoricalResearchPlan, period: Period,
             strategy: str, capital: Decimal):
    """Evaluate one preregistered cell; bars become signals only after availability."""
    if strategy not in (LONG_TERM_ID, SWING_ID):
        raise ValueError("Unknown research hypothesis")
    if dataset.content_digest != plan.dataset_digest:
        raise ValueError("Dataset does not match frozen plan")
    if period not in plan.periods:
        raise ValueError("Period not in frozen plan")
    active_symbols = (plan.symbols if strategy == LONG_TERM_ID
                      else tuple(symbol for symbol in plan.symbols if symbol != "GOOG"))
    selected = [s for s in dataset.sessions if period.start <= s.date() <= period.end]
    quality = dataset.quality_findings((*active_symbols, "VOO"), selected[0], selected[-1]) if selected else ("NO_SESSIONS",)
    fatal = {"EXCHANGE_CALENDAR_UNVERIFIED", "NO_SESSIONS"}
    if set(quality) & fatal or any(q.startswith("MISSING_SESSIONS:") for q in quality):
        return {"strategy_id": strategy, "role": period.role, "capital": str(capital),
                "status": "INVALID_DATA", "data_quality": quality, "trades": (), "curve": (),
                "metrics": {}, "policy_bypasses": 0, "lookahead_violations": 0,
                "research_only": True, "execution_available": False}
    retrospective = not (
        dataset.point_in_time_adjustments and dataset.corporate_actions_complete
    )
    by_key = {(b.symbol, b.session_close): b for b in dataset.bars}
    cash, positions, pending, trades, curve = capital, {}, {}, [], []
    fees_paid, turnover = ZERO, ZERO
    peak = capital
    first_voo = by_key["VOO", selected[0]].close
    held_sessions = {}
    boundary = HistoricalKnowledgeBoundary()
    for index, session in enumerate(selected):
        marks = {s: by_key[s, session].close for s in (*active_symbols, "VOO")}
        # The preceding session alone may submit an order for this close.
        for symbol, order in sorted(pending.items()):
            side, reason, stop = order
            impact = (plan.rules.slippage_bps + plan.rules.spread_bps / 2) / 10000
            price = marks[symbol] * (1 + impact if side == "buy" else 1 - impact)
            target_fraction = (Decimal(1) if capital == plan.experimental_capital
                               else plan.rules.notional_fraction)
            quantity = (
                min((capital * target_fraction / price).to_integral_value(rounding=ROUND_FLOOR),
                    ((cash - plan.rules.commission) / price).to_integral_value(rounding=ROUND_FLOOR))
                if side == "buy" else positions[symbol]["quantity"]
            )
            if side == "buy" and capital == plan.experimental_capital:
                deployed = sum((p["quantity"] * p["entry"] for p in positions.values()), ZERO)
                remaining_sleeve = max(ZERO, Decimal(plan.experimental_capital) - deployed)
                quantity = min(quantity,
                               (remaining_sleeve / price).to_integral_value(rounding=ROUND_FLOOR))
            if quantity <= 0:
                continue
            cost = quantity * price
            if side == "buy":
                cash -= cost + plan.rules.commission
                positions[symbol] = {"quantity": quantity, "entry": price, "stop": stop,
                                     "entered_index": index}
                held_sessions[symbol] = 0
            else:
                cash += cost - plan.rules.commission
                del positions[symbol]
                held_sessions.pop(symbol, None)
            fees_paid += plan.rules.commission
            turnover += cost / capital
            trades.append({"symbol": symbol, "side": side, "quantity": str(quantity),
                           "signal": selected[index - 1].isoformat(),
                           "filled_at": session.isoformat(), "price": str(price),
                           "reason": reason, "policy_status": "NOT_SUBMITTED_RESEARCH_ONLY"})
        pending = {}
        for symbol in positions:
            held_sessions[symbol] += 1
        equity = cash + sum((p["quantity"] * marks[s] for s, p in positions.items()), ZERO)
        peak = max(peak, equity)
        curve.append({"session": session.isoformat(), "equity": str(equity),
                      "drawdown": str(1 - equity / peak),
                      "position_count": len(positions),
                      "deployed_entry_notional": str(sum(
                          (p["quantity"] * p["entry"] for p in positions.values()), ZERO
                      )),
                      "benchmark_equity": str(capital * marks["VOO"] / first_voo)})
        if index == len(selected) - 1:
            break
        next_close = selected[index + 1]
        for symbol in active_symbols:
            history = [by_key[symbol, s] for s in dataset.sessions if s <= session and
                       (symbol, s) in by_key and (
                           retrospective or (
                               by_key[symbol, s].available_at < next_close and
                               by_key[symbol, s].adjustment_known_at <=
                               by_key[symbol, s].available_at
                           )
                       )]
            if not history or history[-1].session_close != session:
                continue
            cutoff = (session if retrospective else
                      max(b.available_at for b in history if b.session_close == session))
            held = positions.get(symbol)
            if strategy == LONG_TERM_ID and index % plan.rules.long_review_sessions != 0 and not held:
                continue
            side, reason, stop = _signal(strategy, history, dataset, symbol, cutoff,
                                         plan.rules, held, held_sessions.get(symbol, 0),
                                         held["stop"] if held else None, boundary)
            if side:
                pending[symbol] = (side, reason, stop)
    final_equity = Decimal(curve[-1]["equity"])
    benchmark_return = Decimal(curve[-1]["benchmark_equity"]) / capital - 1
    metrics = {"observations": len(selected), "number_of_trades": len(trades),
               "closed_trades": sum(t["side"] == "sell" for t in trades),
               "starting_capital": str(capital), "ending_capital": str(final_equity),
               "total_return": str(final_equity / capital - 1),
               "benchmark_return": str(benchmark_return),
               "excess_return": str(final_equity / capital - 1 - benchmark_return),
               "maximum_drawdown": str(max(Decimal(p["drawdown"]) for p in curve)),
               "turnover": str(turnover), "fees": str(fees_paid),
               "ending_cash": str(cash), "cash_utilization": str(1 - cash / final_equity),
               "maximum_simultaneous_positions": max(
                   (point["position_count"] for point in curve), default=0),
               }
    return {"strategy_id": strategy, "role": period.role, "capital": str(capital),
            "status": "COMPLETED", "data_quality": quality, "trades": tuple(trades),
            "curve": tuple(curve), "metrics": metrics, "policy_bypasses": 0,
            "knowledge_exclusions": tuple(boundary.exclusions),
            "lookahead_violations": int(retrospective),
            "evidence_class": ("RETROSPECTIVE_NONQUALIFYING" if retrospective else
                               "POINT_IN_TIME_CANDIDATE"), "research_only": True,
            "execution_available": False}


def historical_gates(rows, gates):
    """Frozen validation gates for candidate statistics; no paper permission."""
    checks = {}
    for name, metric, compare in (
        ("minimum_observations", "observations", lambda a, b: a >= b),
        ("minimum_trades", "number_of_trades", lambda a, b: a >= b),
        ("max_drawdown", "maximum_drawdown", lambda a, b: a <= b),
        ("max_turnover", "turnover", lambda a, b: a <= b),
    ):
        checks[name] = "PASS" if all(
            r["status"] == "COMPLETED" and compare(Decimal(str(r["metrics"][metric])),
                                                   Decimal(str(getattr(gates, name))))
            for r in rows
        ) else "FAIL"
    checks["acceptable_data_quality"] = "PASS" if all(
        set(r["data_quality"]) <= set(gates.acceptable_data_quality) for r in rows
    ) else "FAIL"
    checks["zero_lookahead_violations"] = "PASS" if all(
        r["lookahead_violations"] == 0 for r in rows
    ) else "FAIL"
    checks["zero_policy_bypasses"] = "PASS" if all(
        r["policy_bypasses"] == 0 for r in rows
    ) else "FAIL"
    return checks


def robustness_summary(development, validation):
    """Descriptive period shift only; no holdout or causal robustness claim."""
    summary = []
    for earlier in development:
        later = next(r for r in validation if r["strategy_id"] == earlier["strategy_id"]
                     and r["capital"] == earlier["capital"])
        if earlier["status"] != "COMPLETED" or later["status"] != "COMPLETED":
            summary.append({"strategy_id": earlier["strategy_id"],
                            "capital": earlier["capital"], "status": "UNMEASURABLE"})
            continue
        first, second = earlier["metrics"], later["metrics"]
        summary.append({
            "strategy_id": earlier["strategy_id"], "capital": earlier["capital"],
            "status": "DESCRIPTIVE_ONLY",
            "development_trade_sides": first["number_of_trades"],
            "validation_trade_sides": second["number_of_trades"],
            "return_change": str(Decimal(second["total_return"]) -
                                 Decimal(first["total_return"])),
            "excess_return_change": str(Decimal(second["excess_return"]) -
                                        Decimal(first["excess_return"])),
            "drawdown_change": str(Decimal(second["maximum_drawdown"]) -
                                   Decimal(first["maximum_drawdown"])),
            "turnover_change": str(Decimal(second["turnover"]) -
                                   Decimal(first["turnover"])),
            "holdout_evaluated": False,
            "robustness_established": False,
        })
    return tuple(summary)


class HistoricalResearchStudy:
    """One-way stage transition. OOS is never calculated before validation gates pass."""

    def __init__(self, plan: HistoricalResearchPlan, dataset: HistoricalResearchDataset):
        self.plan = HistoricalResearchPlan.model_validate_json(plan.model_dump_json())
        self.dataset = HistoricalResearchDataset.model_validate_json(dataset.model_dump_json())
        if self.dataset.content_digest != self.plan.dataset_digest:
            raise ValueError("Dataset changed after preregistration")
        self.plan_digest = digest(self.plan)
        self.phase = "PREREGISTERED"
        self.results = {}

    def _stage(self, role):
        if digest(self.plan) != self.plan_digest or digest(self.dataset) != self.plan.dataset_digest:
            raise ValueError("Frozen plan or dataset mutated")
        period = next(p for p in self.plan.periods if p.role == role)
        rows = tuple(simulate(self.dataset, self.plan, period, strategy, capital)
                     for strategy in (LONG_TERM_ID, SWING_ID)
                     for capital in (self.plan.research_capital,
                                     Decimal(self.plan.experimental_capital)))
        self.results[role] = rows
        return rows

    def development(self):
        if self.phase != "PREREGISTERED":
            raise ValueError("Development already exposed")
        rows = self._stage("development")
        period = self.plan.periods[0]
        probes = (
            ("sma_55", {"swing_fast_sessions": 55}),
            ("rsi_52", {"swing_rsi_lower": Decimal(52)}),
            ("atr_2_2", {"swing_stop_atr_multiple": Decimal("2.2")}),
        )
        self.results["sensitivity"] = tuple(
            {"probe": name, "result": simulate(
                self.dataset,
                self.plan.model_copy(update={"rules": ResearchRules.model_validate(
                    self.plan.rules.model_dump() | change)}),
                period, SWING_ID, self.plan.research_capital,
            )}
            for name, change in probes
        )
        self.phase = "DEVELOPMENT_EXPOSED"
        return rows

    def validation(self):
        if self.phase != "DEVELOPMENT_EXPOSED":
            raise ValueError("Validation requires completed development")
        rows = self._stage("validation")
        checks = historical_gates(
            tuple(r for r in rows if r["capital"] == str(self.plan.research_capital)),
            self.plan.gates,
        )
        self.results["experimental_capital_validation_gates"] = historical_gates(
            tuple(r for r in rows if r["capital"] == str(self.plan.experimental_capital)),
            self.plan.gates,
        )
        self.phase = "VALIDATION_PASSED" if all(v == "PASS" for v in checks.values()) else "VALIDATION_FAILED"
        return rows, checks

    def out_of_sample(self):
        # The reserved 2026 interval needs a separate human architecture decision
        # even if historical validation eventually passes. Keep this phase sealed.
        raise ValueError("Untouched OOS requires a separately authorized release")

    def status(self):
        return {"phase": self.phase, "plan_digest": self.plan_digest,
                "forward_paper_sessions": 0, "paper_execution": "DISABLED",
                "production_execution": "DISABLED", "candidate_results_only": True}
