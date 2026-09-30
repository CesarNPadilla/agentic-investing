"""The two initial hypotheses; thresholds remain unapproved and UNSET."""

from datetime import UTC, datetime
from decimal import Decimal

from strategies.experiment_models import ExperimentParameters, MetricRule
from strategies.models import EntryConfig, StrategyVersion, SwingConfig

LONG_TERM_ID = "LONG_TERM_QUALITY_GROWTH"
SWING_ID = "SWING_TREND_MOMENTUM"
LONG_TERM_UNIVERSE = (
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "GOOG",
    "META",
    "TSLA",
    "PLTR",
    "INTC",
)
SWING_UNIVERSE = tuple(s for s in LONG_TERM_UNIVERSE if s != "GOOG")
DEFINITION_TIME = datetime(2026, 9, 30, tzinfo=UTC)


def initial_definitions():
    """Fixed baseline parameters, never selected after observing experiment returns."""
    long_term = StrategyVersion(
        strategy_id=LONG_TERM_ID,
        strategy_version="1.0.0",
        strategy_domain="long_term",
        status="BACKTEST",
        created_at=DEFINITION_TIME,
        configuration=EntryConfig(max_research_age_seconds=86400, allow_test_data=True),
        experiment=ExperimentParameters(
            hypothesis=LONG_TERM_ID,
            permitted_symbols=LONG_TERM_UNIVERSE,
            metric_rules=(
                MetricRule(
                    name="revenue_growth",
                    dimension="growth_durability",
                    metric="revenue_growth",
                    unit="fraction",
                    basis="annual",
                    operator="ge",
                ),
                MetricRule(
                    name="free_cash_flow",
                    dimension="fundamental_quality",
                    metric="free_cash_flow",
                    unit="USD",
                    basis="annual",
                    operator="ge",
                ),
                MetricRule(
                    name="net_debt_to_ebitda",
                    dimension="financial_health",
                    metric="net_debt_to_ebitda",
                    unit="ratio",
                    basis="ttm",
                    operator="le",
                ),
            ),
        ),
    )
    swing = StrategyVersion(
        strategy_id=SWING_ID,
        strategy_version="1.0.0",
        strategy_domain="swing",
        status="BACKTEST",
        created_at=DEFINITION_TIME,
        configuration=EntryConfig(max_research_age_seconds=86400, allow_test_data=True),
        swing=SwingConfig(
            fast_period=50,
            slow_period=200,
            stop_atr_multiple=2,
            max_holding_sessions=20,
            max_holding_days=30,
        ),
        experiment=ExperimentParameters(
            hypothesis=SWING_ID,
            permitted_symbols=SWING_UNIVERSE,
            atr_stop_multiple=2,
            max_holding_sessions=20,
            max_holding_days=30,
        ),
    )
    return long_term, swing


def sensitivity_definitions(baseline):
    """Exactly three one-factor probes, development only; never a Cartesian search."""
    if baseline.strategy_id != SWING_ID:
        return ()
    variants = []
    for label, change in (
        ("sma", {"intermediate_period": 55}),
        ("rsi", {"rsi_lower": Decimal(52)}),
        ("atr", {"atr_stop_multiple": Decimal("2.2")}),
    ):
        parameters = type(baseline.experiment).model_validate(
            baseline.experiment.model_dump() | change
        )
        variants.append(
            StrategyVersion.model_validate(
                baseline.model_dump()
                | {
                    "strategy_version": f"1.0.0-sensitivity.{label}",
                    "experiment": parameters,
                }
            )
        )
    return tuple(variants)
