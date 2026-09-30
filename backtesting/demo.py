"""Explicitly synthetic software demonstration: python -m backtesting.demo."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from agents.long_term.models import (
    Claim,
    Freshness,
    FundamentalData,
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
from backtesting.engine import BacktestEngine
from backtesting.models import BacktestConfig, ExecutionAssumptions, ValidationGates
from backtesting.validation import validate
from portfolio.theses import PositionThesis, ThesisReview
from risk.policy import InvestmentPolicy
from strategies.models import EntryConfig, StrategyVersion


def fixture():
    start = datetime(2024, 1, 2, 21, tzinfo=UTC)
    sessions = tuple(start + timedelta(days=i) for i in (0, 1, 2, 3, 6))
    bars, research, fundamentals = [], [], []
    prices = (100, 99, 98, 101, 102)
    for i, now in enumerate(sessions):
        for symbol, price in (("AAPL", prices[i]), ("VOO", 200 + i)):
            bars.append(
                HistoricalBar(
                    symbol=symbol,
                    session_close=now,
                    available_at=now,
                    open=price,
                    high=price + 1,
                    low=price - 1,
                    close=price,
                    volume=1000,
                )
            )
        source = Source(
            source_id=f"fixture-{i}",
            symbol="AAPL",
            source="SYNTHETIC TEST",
            source_type="other",
            published_at=now,
            retrieved_at=now,
            relevant_claim="software fixture",
            reliable=True,
            is_sample=True,
        )
        fundamental = FundamentalData(symbol="AAPL", retrieved_at=now, sources=(source,))
        fundamentals.append(
            FundamentalObservation(
                observation_id=f"fundamental-{i}", available_at=now, data=fundamental
            )
        )
        claim = Claim(
            text="Synthetic evidence, no investment conclusion",
            evidence_references=(source.source_id,),
        )
        assessment = ResearchAssessment(
            assessment_id=f"assessment-{i}",
            run_id=f"run-{i}",
            scope_id="synthetic",
            symbol="AAPL",
            timestamp=now,
            research_horizon="5-10+ years",
            current_price=Decimal(prices[i]),
            price_currency="USD",
            market_data_timestamp=now,
            fundamental_data_timestamp=now,
            investment_thesis="Software fixture only",
            thesis_status="UNCHANGED",
            positive_drivers=(claim,),
            risks=(claim,),
            catalysts=(claim,),
            invalidation_conditions=("Synthetic invalidation",),
            valuation_context=ValuationContext(status="AVAILABLE", conclusions=(claim,)),
            data_sources=(source,),
            data_quality={
                k: Freshness(state="CURRENT", as_of=now)
                for k in ("market", "fundamentals", "portfolio")
            },
            agent_summary="SYNTHETIC",
            fundamental_data=fundamental,
            review_kind="baseline",
        )
        thesis = PositionThesis(
            account_id="backtest",
            symbol="AAPL",
            thesis_status="ACTIVE",
            current_thesis="Software fixture only",
            last_review_date=now,
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
                observation_id=f"research-{i}",
                available_at=now,
                assessment=assessment,
                thesis=thesis,
            )
        )
    strategy = StrategyVersion(
        strategy_id="fixture-long-term",
        strategy_version="0.1",
        strategy_domain="long_term",
        created_at=start,
        authorization_reference="TEST ONLY",
        configuration=EntryConfig(
            max_research_age_seconds=60,
            allow_test_data=True,
            valuation_decision="ACCEPTABLE",
            portfolio_fit_decision="ACCEPTABLE",
            fixed_notional=100,
        ),
    )
    config = BacktestConfig(
        backtest_id="synthetic-software-demo",
        strategy=strategy,
        risk_policy=InvestmentPolicy(
            max_daily_loss=10,
            max_experimental_loss=20,
            max_state_age_seconds=60,
            daily_loss_timezone="UTC",
        ),
        start_date=sessions[0].date(),
        end_date=sessions[-1].date(),
        initial_capital=160,
        capital_mode="EXPERIMENTAL",
        security_universe=("AAPL",),
        data_source_metadata={"source": "synthetic software fixture"},
        created_at=sessions[-1],
        code_version="backtesting-v0.1-fixture",
        execution=ExecutionAssumptions(
            human_review="ASSUME_APPROVED_FOR_SIMULATION", commission_fixed="0.10", slippage_bps=5
        ),
    )
    data = HistoricalDataset(
        dataset_id="synthetic-five-session",
        version="1",
        source="TEST ONLY",
        calendar_id="synthetic-XNYS-five-closes",
        sessions=sessions,
        bars=tuple(bars),
        fundamentals=tuple(fundamentals),
        research=tuple(research),
        reliable=True,
        is_sample=True,
        corporate_actions_complete=True,
    )
    return config, data


def main():
    import json

    config, data = fixture()
    result = BacktestEngine().run(config, data)
    report = validate((result,), ValidationGates())
    print(
        json.dumps(
            {
                "label": "SYNTHETIC SOFTWARE TEST; NO INVESTMENT CONCLUSIONS",
                "status": result.status,
                "metrics": result.metrics,
                "validation": report.validation_status,
                "eligibility": report.paper_eligibility,
                "forward_paper_sessions": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
