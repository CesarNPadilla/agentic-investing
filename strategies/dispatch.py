"""One shared implementation selector for research, replay and independent review."""

from strategies.engine import LongTermStrategy, SwingStrategy
from strategies.experiments import LongTermQualityGrowthStrategy, SwingTrendMomentumStrategy


def strategy_for(version):
    if version.experiment is not None:
        if version.experiment.hypothesis == "LONG_TERM_QUALITY_GROWTH":
            return LongTermQualityGrowthStrategy()
        return SwingTrendMomentumStrategy()
    return LongTermStrategy() if version.strategy_domain == "long_term" else SwingStrategy()
