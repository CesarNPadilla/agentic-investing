"""Internal service ready for a future authenticated dashboard; no scheduler."""

import itertools

from backtesting.engine import BacktestEngine
from backtesting.validation import compare, validate
from risk.evaluator import digest


class BacktestingService:
    def __init__(self, registry):
        self.registry = registry

    def run(self, config, dataset, gates, *, notes=""):
        result = BacktestEngine().run(config, dataset)
        report = validate((result,), gates)
        self.registry.save(result, dataset, report, notes)
        return result, report

    def walk_forward(self, experiments, gates):
        """Explicit nonoverlapping holdout folds, no fitting or parameter search.

        Each fold starts with configured cash. Curves are compared, not spliced into
        an artificial continuous portfolio. Caller supplies all reviewed folds.
        """
        experiments = tuple(experiments)
        if not experiments:
            raise ValueError("At least one fold required")
        configs = [config for config, _ in experiments]
        if len({digest(c.strategy) for c in configs}) != 1:
            raise ValueError("Walk-forward requires one frozen strategy definition")
        if any(not c.periods or c.evaluated_role != "out_of_sample" for c in configs):
            raise ValueError("Walk-forward folds require explicit holdout periods")
        if any(a.end_date >= b.start_date for a, b in itertools.pairwise(configs)):
            raise ValueError("Walk-forward folds must be ordered and nonoverlapping")
        results = tuple(self.run(config, dataset, gates)[0] for config, dataset in experiments)
        return compare(results), validate(results, gates)
