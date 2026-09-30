"""Human-readable factual review; external text is escaped, never interpreted."""

import html


def safe(value):
    return (
        html.escape(str(value), quote=True)
        .replace("|", "&#124;")
        .replace("\n", " ")
        .replace("`", "&#96;")
    )


def markdown(plan, lab):
    synthetic = any("SYNTHETIC_TEST_DATA" in r["data_quality"] for r in lab.results)
    label = "SYNTHETIC SOFTWARE EXPERIMENTS" if synthetic else "HISTORICAL RESEARCH EXPERIMENTS"
    lines = [
        "# Strategy Experiment Lab v0.1 — human review",
        "",
        f"**{label} — NOT INVESTMENT RECOMMENDATIONS.**",
        "",
        "The dates below label generated fixtures, not observed market performance."
        if synthetic
        else "Historical provenance and all quality findings require human review.",
        "No optimization, winner selection, broker orders or forward-paper trading occurred.",
        "",
        f"Plan: `{safe(plan.plan_id)}`; immutable fingerprint: `{lab.plan_digest}`.",
        "",
        "Research → Thesis → Opportunity → Strategy → Backtest → Validation → Human Review → Future Paper Eligibility.",
        "",
        "## Data and assumptions",
        "",
        "Period datasets are physically separated; only earlier indicator warm-up is retained. Synthetic calendars are not exchange-certified."
        if synthetic
        else "Dataset pins bind the exact sources, periods and causal warm-up.",
        "",
        "| Role | Start | End |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {p.role} | {p.start} | {p.end} |" for p in plan.periods]
    assumptions = sorted({str(r.config.execution.model_dump(mode="json")) for r in plan.runs})
    capital = sorted({(r.config.capital_mode, str(r.config.initial_capital)) for r in plan.runs})
    lines += [
        "",
        "Execution assumptions: " + safe(assumptions) + ".",
        "Capital modes/cash: "
        + safe(capital)
        + ". Current policy permits only whole-share buys and USD 160 attributed acquisitions; larger synthetic research cash does not expand that sleeve.",
        "",
        "All dataset pins, exact definitions, assumptions, metrics, diagnostics and exposure receipts are in the JSON artifact and local registry.",
        "",
    ]
    for definition in plan.hypotheses:
        sid = definition.strategy_id
        report = next(v for v in lab.validation if v["strategy_id"] == sid)
        rows = [r for r in lab.results if r["strategy_id"] == sid and r["purpose"] == "baseline"]
        p = definition.experiment
        lines += [
            f"## {sid} v{definition.strategy_version}",
            "",
            f"Domain: {definition.strategy_domain.upper()}; status: BACKTEST.",
            "",
        ]
        if definition.strategy_domain == "long_term":
            lines += [
                "Hypothesis: durable growth, business/fundamental quality and financial health can support infrequent 5–10+ year allocations with reviewed valuation and portfolio fit.",
                "Rules: separately sourced fundamental, financial-health and growth gates; business/growth evidence; supported active thesis; valuation and concentration review. Exact thresholds: "
                + safe(
                    [
                        (r.metric, r.operator, r.threshold if r.threshold is not None else "UNSET")
                        for r in p.metric_rules
                    ]
                )
                + ".",
                "Thesis/fundamental/health/catalyst deterioration creates EXIT_REVIEW, never a price-only automatic sell.",
            ]
        else:
            lines += [
                "Hypothesis: a simple, unoptimized trend/momentum framework is a useful controlled research baseline.",
                f"Rules: close > SMA({p.trend_period}), SMA({p.intermediate_period}) > SMA({p.trend_period}), {p.rsi_lower} < RSI({p.rsi_period}) < {p.rsi_upper}; volume filter={p.require_volume}, prior {p.volume_period} sessions. ATR({p.atr_period}), {p.atr_stop_multiple}× entry-ATR stop, {p.max_holding_sessions} sessions/{p.max_holding_days} days are explicit experimental review parameters.",
                "Review exits on close below intermediate SMA, trend failure, holding limit or ATR stop. Existing swing forward-evidence gate remains enforced.",
            ]
        lines += [
            "",
            "Universe: "
            + ", ".join(definition.experiment.permitted_symbols)
            + ". Research membership grants no purchase permission. VOO is the benchmark, not a required holding.",
            "",
            "| Period | Capital mode | Return | VOO return | Max drawdown | VOO drawdown | Fills | Utilization |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for r in rows:
            m = r["metrics"]
            lines.append(
                "| "
                + " | ".join(
                    safe(v)
                    for v in (
                        r["role"],
                        r["capital_mode"],
                        m.get("total_return"),
                        m.get("benchmark_return"),
                        m.get("maximum_drawdown"),
                        m.get("benchmark_maximum_drawdown"),
                        m.get("number_of_trades"),
                        m.get("cash_utilization"),
                    )
                )
                + " |"
            )
        weaknesses = sorted({name for r in rows for name in r["diagnostics"]["failed_gates"]})
        fills = sum(r["metrics"].get("number_of_trades", 0) for r in rows)
        risk_exercised = any(r["diagnostics"]["risk_review_exercised"] for r in rows)
        lines += [
            "",
            "Diagnostics: " + ", ".join(safe(x) for x in weaknesses) + ".",
            "",
            f"What happened: {fills} filled sides across independent baseline runs. Risk review exercised={risk_exercised}. Zero fills/cash-only curves do not demonstrate strategy success. Gate failures above explain blocked entries; unit tests separately exercise risk submission paths.",
            "Largest weaknesses: unresolved controls listed below, policy/universe restrictions and no production-grade liquidity/settlement model. No closed trades means undefined win rate/profit factor/holding period; an UNSET risk-free rate or zero variance prevents meaningful Sharpe/Sortino values.",
            "Bias review: "
            + safe(sorted({w for r in rows for w in r["bias_warnings"]}))
            + ". Synthetic results provide no real bull/bear/rate-tightening/AI-expansion coverage. OOS exposure was reserved before evaluation and cannot be relabeled unseen.",
            "Data quality: " + safe(sorted({q for r in rows for q in r["data_quality"]})) + ".",
            "USD 160 behavior: fractional requirements and whole-share prices are listed per period in JSON. Fractional orders remain blocked by policy; minimum practical size is UNSET. No claim that USD 100,000 behavior translates to USD 160.",
            "",
            f"Validation: **{report['validation_status']}**. Conclusion: **{report['paper_eligibility']}**. Human review remains required.",
            "Unresolved controls: " + ", ".join(safe(x) for x in report["unresolved_risks"]) + ".",
            "",
        ]
    lines += [
        "## Limited sensitivity",
        "",
        "Preregistered development-only, one-factor probes: SMA(50)→55; RSI lower bound 50→52; ATR multiple 2→2.2. No Cartesian combinations, ranking, tuning or automatic selection.",
        "",
    ]
    for probe in lab.sensitivity:
        lines.append(
            f"- {safe(probe['version'])}: technical gate counts changed={probe['gate_counts_changed']}; metric differences={safe(probe['metric_changes'])}. {safe(probe['conclusion'])}."
        )
    lines += [
        "",
        "## Human review boundary",
        "",
        "Conclusions: "
        + safe({r["strategy_id"]: r["paper_eligibility"] for r in lab.validation})
        + ". Zero historical/OOS/synthetic sessions count toward the required **60 sequential non-synthetic forward-paper market sessions**. Production execution remains DISABLED.",
        "Next: acquire provenance-validated historical market/fundamental/thesis evidence and review the UNSET controls and simulation-policy constraints. Do not begin forward paper trading automatically.",
        "",
    ]
    return "\n".join(lines)
