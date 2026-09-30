"""Deterministic synthetic data ONLY. Dates resemble sessions, not real market history."""

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from agents.long_term.models import (
    Claim,
    Freshness,
    FundamentalData,
    Metric,
    ResearchAssessment,
    Source,
    ValuationContext,
)
from backtesting.data import (
    FundamentalObservation,
    HistoricalBar,
    HistoricalDataset,
    ResearchObservation,
)
from backtesting.models import BacktestConfig, ExecutionAssumptions, Period
from experiment_lab.definitions import (
    DEFINITION_TIME,
    LONG_TERM_UNIVERSE,
    initial_definitions,
    sensitivity_definitions,
)
from experiment_lab.models import DatasetPin, ExperimentPlan, PlannedRun
from portfolio.theses import PositionThesis, ThesisReview
from risk.evaluator import digest
from risk.policy import InvestmentPolicy
from technical.indicators import SessionBar, SessionHistory

WARMUP = 220
PERIOD_SESSIONS = 6


def synthetic_archive():
    sessions = []
    day = datetime(2020, 1, 2, 21, tzinfo=UTC)
    while len(sessions) < WARMUP + 3 * PERIOD_SESSIONS:
        if day.weekday() < 5:
            sessions.append(day)
        day += timedelta(days=1)
    sessions = tuple(sessions)
    bars, research, fundamentals, histories = [], [], [], []
    prices = (100, 200, 80, 150, 120, 121, 250, 220, 25, 30, 300)
    for index, (symbol, base) in enumerate(zip((*LONG_TERM_UNIVERSE, "VOO"), prices)):
        symbol_bars = []
        for i, now in enumerate(sessions):
            # Fixed rise/decline/rebound segments, selected before any strategy outcomes.
            phase = max(0, (i - WARMUP) // PERIOD_SESSIONS)
            drift = Decimal(i) / 2000
            if phase == 1:
                drift -= Decimal(i - WARMUP - PERIOD_SESSIONS + 1) / 120
            elif phase == 2:
                drift -= Decimal("0.05")
                drift += Decimal(i - WARMUP - 2 * PERIOD_SESSIONS + 1) / 150
            triangle = Decimal(5 - abs(5 - i % 10) - 2) / 200
            price = (Decimal(base) * (1 + drift + triangle)).quantize(Decimal("0.0001"))
            volume = Decimal(100000 + (i % 5) * 10000 + index * 100)
            bar = HistoricalBar(
                symbol=symbol,
                session_close=now,
                available_at=now,
                open=price,
                close=price,
                high=price + 1,
                low=price - 1,
                volume=volume,
            )
            bars.append(bar)
            symbol_bars.append(SessionBar.model_validate(bar.model_dump(exclude={"symbol"})))
            if i < WARMUP or symbol == "VOO":
                continue
            end = now.date() - timedelta(days=30)
            start = end - timedelta(days=364)
            source = Source(
                source_id=f"synthetic-{symbol}-{i}",
                symbol=symbol,
                source="GENERATED SOFTWARE FIXTURE; NOT HISTORICAL SEC DATA",
                source_type="other",
                published_at=now,
                retrieved_at=now,
                period_start=start,
                period_end=end,
                relevant_claim="Synthetic numbers and thesis for software verification only",
                reliable=True,
                is_sample=True,
            )
            claim = Claim(
                text="Synthetic evidence; no claim about this issuer",
                evidence_references=(source.source_id,),
            )
            metrics = tuple(
                Metric(
                    name=name,
                    value=value,
                    unit=unit,
                    source_id=source.source_id,
                    period_start=start,
                    period_end=end,
                    basis=basis,
                )
                for name, value, unit, basis in (
                    ("revenue_growth", Decimal("0.12"), "fraction", "annual"),
                    ("free_cash_flow", Decimal(1000000000), "USD", "annual"),
                    ("net_debt_to_ebitda", Decimal(2), "ratio", "ttm"),
                )
            )
            fundamental = FundamentalData(
                symbol=symbol, retrieved_at=now, sources=(source,), metrics=metrics
            )
            fundamentals.append(
                FundamentalObservation(
                    observation_id=f"fundamentals-{symbol}-{i}", available_at=now, data=fundamental
                )
            )
            assessment = ResearchAssessment(
                assessment_id=f"assessment-{symbol}-{i}",
                run_id=f"research-{symbol}-{i}",
                scope_id="SYNTHETIC",
                symbol=symbol,
                timestamp=now,
                research_horizon="5-10+ years",
                current_price=price,
                price_currency="USD",
                market_data_timestamp=now,
                fundamental_data_timestamp=now,
                investment_thesis="Synthetic software hypothesis only",
                thesis_status="UNCHANGED",
                positive_drivers=(claim,),
                risks=(claim,),
                catalysts=(claim,),
                competitive_position=(claim,),
                growth_context=(claim,),
                financial_health=(claim,),
                invalidation_conditions=("Synthetic invalidation",),
                data_sources=(source,),
                metrics=metrics,
                fundamental_data=fundamental,
                valuation_context=ValuationContext(status="AVAILABLE", conclusions=(claim,)),
                data_quality={
                    k: Freshness(state="CURRENT", as_of=now)
                    for k in ("market", "fundamentals", "portfolio")
                },
                agent_summary="SYNTHETIC FIXTURE; NOT RECOMMENDATION",
                review_kind="baseline",
            )
            thesis = PositionThesis(
                account_id="backtest",
                symbol=symbol,
                thesis_status="ACTIVE",
                current_thesis="Synthetic software hypothesis only",
                last_review_date=now,
                secondary_classifications=("SWING_ELIGIBLE",),
                agent_review_history=(
                    ThesisReview(
                        review_id=assessment.assessment_id,
                        agent="fixture",
                        reviewed_at=now,
                        assessment="UNCHANGED",
                    ),
                ),
            )
            research.append(
                ResearchObservation(
                    observation_id=f"research-observation-{symbol}-{i}",
                    available_at=now,
                    assessment=assessment,
                    thesis=thesis,
                )
            )
        histories.append(
            SessionHistory(
                symbol=symbol,
                source="synthetic unadjusted-equivalent vintage; no actions",
                calendar_id="SYNTHETIC-WEEKDAYS-NOT-EXCHANGE-CERTIFIED",
                sessions=sessions,
                bars=tuple(symbol_bars),
                adjustment="all",
                adjustment_known_at=sessions[0],
                reliable=True,
                is_sample=True,
            )
        )
    return HistoricalDataset(
        dataset_id="LAB-SYNTHETIC-NOT-MARKET-HISTORY",
        version="1",
        source="deterministic formula v1",
        calendar_id="SYNTHETIC-WEEKDAYS-NOT-EXCHANGE-CERTIFIED",
        sessions=sessions,
        bars=tuple(bars),
        research=tuple(research),
        fundamentals=tuple(fundamentals),
        indicator_vintages=tuple(histories),
        reliable=True,
        is_sample=True,
        corporate_actions_complete=True,
    )


def period_dataset(archive, period):
    """Physically omit later-period rows, retaining only causal indicator warm-up."""
    sessions = tuple(t for t in archive.sessions if t.date() <= period.end)
    cutoff = sessions[-1]
    payload = archive.model_dump() | {
        "dataset_id": archive.dataset_id + "-" + period.role,
        "sessions": sessions,
        "bars": tuple(b for b in archive.bars if b.available_at <= cutoff),
        "research": tuple(
            r for r in archive.research if period.start <= r.available_at.date() <= period.end
        ),
        "fundamentals": tuple(f for f in archive.fundamentals if f.available_at <= cutoff),
        "indicator_vintages": tuple(
            SessionHistory.model_validate(
                h.model_dump()
                | {
                    "sessions": sessions,
                    "bars": tuple(b for b in h.bars if b.available_at <= cutoff),
                }
            )
            for h in archive.indicator_vintages
        ),
    }
    return HistoricalDataset.model_validate(payload)


def demonstration_plan():
    archive = synthetic_archive()
    periods = tuple(
        Period(
            role=role,
            start=archive.sessions[WARMUP + i * PERIOD_SESSIONS].date(),
            end=archive.sessions[WARMUP + (i + 1) * PERIOD_SESSIONS - 1].date(),
        )
        for i, role in enumerate(("development", "validation", "out_of_sample"))
    )
    definitions = initial_definitions()
    datasets, pins = {}, {}
    for period in periods:
        data = period_dataset(archive, period)
        fingerprint = digest(data)
        datasets[fingerprint] = data
        pins[period.role] = DatasetPin(
            dataset_id=data.dataset_id,
            version=data.version,
            content_digest=fingerprint,
            lineage="SYNTHETIC-FORMULA-V1",
        )
    root = Path(__file__).resolve().parents[1]
    files = sorted(
        path
        for package in (
            "experiment_lab",
            "strategies",
            "risk",
            "backtesting",
            "technical",
            "portfolio",
            "agents/long_term",
        )
        for path in (root / package).glob("*.py")
    )
    source_hash = hashlib.sha256()
    for path in files:
        source_hash.update(path.relative_to(root).as_posix().encode())
        source_hash.update(path.read_bytes().replace(b"\r\n", b"\n"))
    code_version = "lab-v0.1-source-sha256:" + source_hash.hexdigest()
    runs = []
    for definition in definitions:
        for mode, capital in (("STRATEGY_RESEARCH", 100000), ("EXPERIMENTAL", 160)):
            for period in periods:
                config = BacktestConfig(
                    backtest_id=f"lab-v1-{definition.strategy_id}-{mode}-{period.role}",
                    strategy=definition,
                    risk_policy=InvestmentPolicy(),
                    start_date=period.start,
                    end_date=period.end,
                    initial_capital=capital,
                    capital_mode=mode,
                    security_universe=definition.experiment.permitted_symbols,
                    periods=periods,
                    evaluated_role=period.role,
                    evaluation_frequency="monthly"
                    if definition.strategy_domain == "long_term"
                    else "daily",
                    execution=ExecutionAssumptions(
                        commission_fixed="0.10",
                        commission_bps=0,
                        slippage_bps=5,
                        spread_bps=2,
                        fractional_shares=(mode == "EXPERIMENTAL"),
                    ),
                    data_source_metadata={
                        "kind": "SYNTHETIC SOFTWARE ONLY",
                        "dividends": "NONE IN FIXTURE",
                        "corporate_actions": "NONE IN FIXTURE; complete synthetic action ledger",
                    },
                    created_at=DEFINITION_TIME,
                    code_version=code_version,
                )
                runs.append(PlannedRun(config=config, dataset=pins[period.role]))
    baseline = next(
        r
        for r in runs
        if r.config.strategy.strategy_domain == "swing"
        and r.config.capital_mode == "STRATEGY_RESEARCH"
        and r.config.evaluated_role == "development"
    )
    for version in sensitivity_definitions(baseline.config.strategy):
        config = BacktestConfig.model_validate(
            baseline.config.model_dump()
            | {
                "backtest_id": "lab-v1-" + version.strategy_id + "-" + version.strategy_version,
                "strategy": version,
            }
        )
        runs.append(PlannedRun(config=config, dataset=baseline.dataset, purpose="sensitivity"))
    return ExperimentPlan(
        plan_id="strategy-experiment-lab-v1-synthetic",
        created_at=DEFINITION_TIME,
        hypotheses=definitions,
        periods=periods,
        runs=tuple(runs),
    ), datasets
