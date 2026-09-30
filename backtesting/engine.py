"""Offline orchestrator reusing production research strategies and policy review."""

from decimal import Decimal

from agents.long_term.models import PortfolioContext
from backtesting.analytics import metrics
from backtesting.data import HistoricalDataset, LookaheadViolation, quality, snapshot
from backtesting.models import BacktestConfig, BacktestResult
from backtesting.portfolio import PortfolioSimulator
from risk.evaluator import KillSwitch, digest, evaluate
from risk.proposals import TradeProposal
from strategies.engine import LongTermStrategy, SwingStrategy
from strategies.opportunities import OpportunityEngine
from strategies.review import review_strategy_proposal


def stable_proposal(proposal, identity):
    payload = proposal.model_dump(exclude={"proposal_digest"}) | {"proposal_id": identity}
    return TradeProposal(**payload, proposal_digest=digest(payload))


def permitted(status, config):
    return status == "PASS" or (
        status == "REQUIRE_HUMAN_REVIEW"
        and config.execution.human_review == "ASSUME_APPROVED_FOR_SIMULATION"
    )


class BacktestEngine:
    def run(self, config: BacktestConfig, dataset: HistoricalDataset) -> BacktestResult:
        # Revalidate/copy to reject model_construct/model_copy bypasses and isolate caller mutation.
        config = BacktestConfig.model_validate_json(config.model_dump_json())
        dataset = HistoricalDataset.model_validate_json(dataset.model_dump_json())
        findings = list(quality(dataset, config))
        warnings = ["HISTORICAL_SESSIONS_DO_NOT_COUNT_TOWARD_60_FORWARD_SESSIONS"]
        if config.universe_scope == "targeted":
            warnings.append("CONDITIONAL_ON_SELECTED_SECURITIES")
        elif not dataset.point_in_time_universe_complete or not dataset.universes:
            warnings.append("SURVIVORSHIP_BIAS_RISK")
        if not config.periods or config.evaluated_role == "development":
            warnings.append("IN_SAMPLE_EVALUATION")
        if config.strategy.created_at.date() > config.start_date:
            warnings.append("RETROSPECTIVE_STRATEGY_DEFINITION")
        if config.capital_mode == "STRATEGY_RESEARCH":
            warnings.append(
                "SYNTHETIC_CAPITAL_SEPARATE_FROM_REAL_PORTFOLIO_POLICY_CAP_STILL_APPLIES"
            )
        curve, decisions, pending = [], [], []
        portfolio = PortfolioSimulator(config)
        status, violations = "COMPLETED", 0
        fatal = {
            "TIMESTAMP_INCONSISTENCIES",
            "DUPLICATE_OBSERVATIONS",
            "MISSING_SESSIONS",
            "INCOMPLETE_BENCHMARK_DATA",
            "MISSING_CORPORATE_ACTIONS",
            "UNRELIABLE_DATA",
            "UNSUPPORTED_CORPORATE_ACTION",
            "UNSUPPORTED_DIVIDEND_SCHEDULE",
            "INTERVAL_ENDPOINT_NOT_SESSION",
            "INDICATOR_CALENDAR_MISMATCH",
            "INCOMPLETE_POINT_IN_TIME_UNIVERSE",
        }
        sessions = [s for s in dataset.sessions if config.start_date <= s.date() <= config.end_date]
        if fatal.intersection(findings) or len(sessions) < 2:
            status = "INVALID_DATA"
        else:
            implementation = (
                LongTermStrategy()
                if config.strategy.strategy_domain == "long_term"
                else SwingStrategy()
            )
            opening = portfolio.initial_state(sessions[0])
            peak = config.initial_capital
            previous_marks = {}
            benchmark_units, benchmark_cash = None, Decimal(0)
            last_evaluation = None
            seen_research = {}
            try:
                for now in sessions:
                    view = snapshot(dataset, now, config.security_universe)
                    bars = {b.symbol: b for b in view.bars if b.session_close == now}
                    marks = {s: b.close for s, b in bars.items()}
                    portfolio.begin_day(now, previous_marks)
                    for action in sorted(
                        dataset.actions,
                        key=lambda a: (a.effective_at, a.kind != "split", a.action_id),
                    ):
                        if action.effective_at != now:
                            continue
                        portfolio.action(action)
                        # Quantity transformations invalidate pending share instructions.
                        if action.kind == "split":
                            for proposal in pending:
                                if proposal.trade.symbol == action.symbol:
                                    decisions.append(
                                        {
                                            "timestamp": now.isoformat(),
                                            "proposal_id": proposal.proposal_id,
                                            "fill_status": "CANCELLED_CORPORATE_ACTION",
                                        }
                                    )
                            pending = [p for p in pending if p.trade.symbol != action.symbol]
                        if action.symbol == config.benchmark and benchmark_units is not None:
                            if action.kind == "split":
                                benchmark_units *= action.ratio
                            elif config.benchmark_basis == "total_return":
                                benchmark_cash += benchmark_units * action.cash_per_share
                    if benchmark_units is None:
                        benchmark_units = config.initial_capital / marks[config.benchmark]
                    if benchmark_cash:
                        benchmark_units += benchmark_cash / marks[config.benchmark]
                        benchmark_cash = Decimal(0)
                    for proposal in pending:
                        symbol = proposal.trade.symbol
                        price, fee = portfolio.quote(
                            proposal.trade.side, proposal.trade.quantity, marks[symbol]
                        )
                        state = portfolio.state(now, marks, opening.as_of)
                        trade = proposal.trade.model_copy(
                            update={"limit_price": price, "estimated_fees": fee}
                        )
                        risk = evaluate(
                            config.risk_policy,
                            opening,
                            state,
                            trade,
                            KillSwitch(enabled=False, as_of=now),
                            now=now,
                        )
                        fill_status = "RISK_BLOCKED"
                        if permitted(risk.status, config):
                            if proposal.trade.side == "buy" and price > proposal.trade.limit_price:
                                fill_status = "LIMIT_PRICE_EXCEEDED"
                            else:
                                fill_status = portfolio.fill(
                                    proposal, now, price, fee, marks, risk.model_dump(mode="json")
                                )
                        decisions.append(
                            {
                                "timestamp": now.isoformat(),
                                "stage": "execution_recheck",
                                "proposal_id": proposal.proposal_id,
                                "risk_status": risk.status,
                                "risk": risk.model_dump(mode="json"),
                                "fill_status": fill_status,
                            }
                        )
                    pending = []
                    state = portfolio.state(now, marks, opening.as_of)
                    frequency = config.evaluation_frequency
                    due = (
                        last_evaluation is None
                        or frequency in {"daily", "event_driven"}
                        or (
                            frequency == "weekly"
                            and now.isocalendar()[:2] != last_evaluation.isocalendar()[:2]
                        )
                        or (
                            frequency == "monthly"
                            and (now.year, now.month)
                            != (last_evaluation.year, last_evaluation.month)
                        )
                    )
                    if due:
                        for symbol in sorted(
                            set(config.security_universe).intersection(view.universe)
                        ):
                            candidates = [r for r in view.research if r.assessment.symbol == symbol]
                            if not candidates:
                                decisions.append(
                                    {
                                        "timestamp": now.isoformat(),
                                        "symbol": symbol,
                                        "strategy_status": "INSUFFICIENT_DATA",
                                        "reasons": ["historical_research_unavailable"],
                                    }
                                )
                                continue
                            observation = max(
                                candidates, key=lambda r: (r.available_at, r.observation_id)
                            )
                            if (
                                frequency == "event_driven"
                                and seen_research.get(symbol) == observation.observation_id
                            ):
                                continue
                            seen_research[symbol] = observation.observation_id
                            assessment, thesis = observation.assessment, observation.thesis
                            if thesis.account_id != config.account_id or thesis.symbol != symbol:
                                findings.append("HISTORICAL_THESIS_SCOPE_MISMATCH")
                                continue
                            if (
                                assessment.current_price != marks[symbol]
                                or assessment.market_data_timestamp != now
                            ):
                                decisions.append(
                                    {
                                        "timestamp": now.isoformat(),
                                        "symbol": symbol,
                                        "strategy_status": "INSUFFICIENT_DATA",
                                        "reasons": ["historical_research_mark_mismatch"],
                                    }
                                )
                                continue
                            # Only simulated portfolio facts are recomputed; research and theses are not invented.
                            position = portfolio.positions.get(symbol)
                            equity = portfolio.equity(marks)
                            value = position["quantity"] * marks[symbol] if position else Decimal(0)
                            context = PortfolioContext(
                                observation_id=digest(state),
                                as_of=now,
                                actual_symbols=tuple(p.symbol for p in state.positions),
                                current_allocation=value / equity if equity else None,
                                current_market_value=value,
                                cost_basis=position["basis"] if position else None,
                            )
                            assessment = assessment.model_copy(update={"portfolio_fit": context})
                            opportunity = OpportunityEngine().identify(
                                assessment,
                                thesis,
                                state,
                                config.risk_policy,
                                config.strategy.configuration,
                                now=now,
                                domain=config.strategy.strategy_domain,
                            )
                            identity = digest(
                                (config.backtest_id, symbol, now, observation.observation_id)
                            )
                            opportunity = opportunity.model_copy(
                                update={"opportunity_id": identity}
                            )
                            # Conservative known commission estimate; actual notional fees rechecked at fill.
                            budget = (
                                config.strategy.configuration.fixed_notional
                                or config.strategy.swing.max_notional
                                or Decimal(0)
                            )
                            fees = (
                                config.execution.commission_fixed
                                + budget * config.execution.commission_bps / 10000
                            )
                            result = implementation.evaluate(
                                opportunity,
                                assessment,
                                thesis,
                                state,
                                config.risk_policy,
                                config.strategy,
                                now=now,
                                fees=fees,
                                history=view.history(symbol),
                                historical_replay=True,
                            )
                            decision = {
                                "timestamp": now.isoformat(),
                                "symbol": symbol,
                                "strategy_status": result.status,
                                "reasons": result.reasons,
                                "opportunity": opportunity.model_dump(mode="json"),
                                "research_observation_id": observation.observation_id,
                            }
                            if result.proposal:
                                proposal = stable_proposal(result.proposal, identity + "-proposal")
                                review = review_strategy_proposal(
                                    config.risk_policy,
                                    opening,
                                    state,
                                    proposal,
                                    KillSwitch(enabled=False, as_of=now),
                                    thesis,
                                    opportunity,
                                    assessment,
                                    config.strategy,
                                    now=now,
                                    history=view.history(symbol),
                                    historical_replay=True,
                                )
                                decision.update(
                                    proposal=proposal.model_dump(mode="json"),
                                    risk_status=review.status,
                                    review=review.model_dump(mode="json"),
                                )
                                if permitted(review.status, config):
                                    pending.append(proposal)
                            decisions.append(decision)
                        last_evaluation = now
                    benchmark_equity = benchmark_units * marks[config.benchmark]
                    curve.append(portfolio.record(now, marks, benchmark_equity, peak))
                    peak = max(peak, portfolio.equity(marks))
                    opening = state
                    previous_marks = marks
                if pending:
                    warnings.append("FINAL_SIGNALS_UNFILLED")
            except LookaheadViolation:
                status, violations = "LOOKAHEAD_VIOLATION", 1
                findings.append("FUTURE_EVIDENCE_IN_AVAILABLE_RECORD")
        return BacktestResult(
            config=config,
            dataset_digest=digest(dataset),
            input_digest=digest((config, dataset)),
            status=status,
            metrics=metrics(config, curve, portfolio.trades, decisions),
            equity_curve=tuple(curve),
            decisions=tuple(decisions),
            trades=tuple(portfolio.trades),
            data_quality=tuple(sorted(set(findings))),
            bias_warnings=tuple(warnings),
            lookahead_violations=violations,
        )
