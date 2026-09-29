"""Plain, escaped Markdown export of persisted research; never recomputes evidence."""

from html import escape

from reports.models import ResearchReport


def safe(value) -> str:
    text = escape(" ".join(str(value).split()), quote=True)
    for character in "\\`*_{}[]()#+-.!|":
        text = text.replace(character, "\\" + character)
    return text


def render_markdown(report: ResearchReport) -> str:
    lines = [
        f"# {safe(report.symbol)} investment research",
        "",
        (
            f"Report: {report.id} | Generated: {report.generated_at.isoformat()} | "
            f"Schema: {report.schema_version} | Status: {report.status}"
        ),
        "",
        safe(report.summary),
        "",
        "## Price and provenance",
        "",
        (
            f"{report.quote.price} {report.quote.currency}; source: {safe(report.quote.source)}; "
            f"as of {report.quote.as_of.isoformat()}; synthetic: {report.quote.is_sample}."
        ),
    ]

    def section(title, items):
        lines.extend(["", f"## {title}", ""])
        lines.extend(f"- {safe(item)}" for item in items)
        if not items:
            lines.append("Unavailable or no observations in supplied evidence.")

    if report.technicals:
        technical = report.technicals
        section(
            "Technical indicators",
            [
                f"{name}: {getattr(technical, name)}"
                for name in type(technical).model_fields
                if name != "missing_indicators"
            ],
        )
        if report.price_history:
            lines.extend(
                [
                    "",
                    (
                        f"History source: {safe(report.price_history.source)}; "
                        f"adjustment: {report.price_history.adjustment}; "
                        f"synthetic: {report.price_history.is_sample}."
                    ),
                ]
            )
    else:
        section("Technical indicators", [])
    fundamental = report.fundamentals
    section(
        "Fundamentals",
        [
            f"{name}: {getattr(fundamental, name)}"
            for name in (
                "revenue_growth",
                "net_margin",
                "free_cash_flow",
                "current_ratio",
                "debt_to_equity",
                "net_debt",
            )
        ]
        if fundamental
        else [],
    )
    if fundamental:
        lines.extend(
            [
                "",
                (
                    f"Source: {safe(fundamental.evidence.source)}; "
                    f"currency: {fundamental.evidence.currency}; "
                    f"retrieved: {fundamental.evidence.retrieved_at.isoformat()}; "
                    f"synthetic: {fundamental.evidence.is_sample}."
                ),
            ]
        )
        for statement in (fundamental.evidence.current, fundamental.evidence.previous):
            if statement:
                lines.extend(
                    [
                        "",
                        safe(
                            f"Period {statement.period_start} through {statement.period_end}; "
                            f"filed {statement.filed_at.isoformat()}; source {statement.source_url}"
                        ),
                    ]
                )
    section("News and catalysts", report.catalysts)
    if report.news:
        evidence = report.news.evidence
        lines.extend(
            [
                "",
                safe(
                    f"Source: {evidence.source}; retrieved {evidence.retrieved_at.isoformat()}; "
                    f"window begins {evidence.window_start.isoformat()}; synthetic: {evidence.is_sample}."
                ),
            ]
        )
        for article in evidence.articles:
            lines.extend(
                [
                    "",
                    safe(
                        f"{article.id}: {article.headline} — {article.publisher}; "
                        f"{article.published_at.isoformat()}; {article.url}"
                    ),
                ]
            )
    portfolio = report.portfolio
    section(
        "Portfolio exposure",
        [
            f"{name}: {getattr(portfolio, name)}"
            for name in (
                "state",
                "equity",
                "cash_value",
                "long_value",
                "short_value",
                "gross_exposure",
                "net_exposure",
                "gross_leverage",
                "net_leverage",
                "cash_weight",
            )
        ]
        if portfolio
        else [],
    )
    if portfolio:
        lines.extend(
            [
                "",
                safe(
                    f"Source: {portfolio.evidence.source}; as of {portfolio.evidence.as_of.isoformat()}; "
                    f"currency: {portfolio.evidence.currency}; synthetic: {portfolio.evidence.is_sample}."
                ),
            ]
        )
        for name in ("by_symbol", "by_sector", "by_account"):
            for key, value in sorted(getattr(portfolio, name).items()):
                lines.extend(
                    [
                        "",
                        safe(
                            f"{name} / {key}: net {value.net_value}; gross {value.gross_value}; "
                            f"net weight {value.net_weight}; gross weight {value.gross_weight}."
                        ),
                    ]
                )
    section("Supporting observations", report.bull_case)
    section("Counter observations", report.bear_case)
    section(
        "Risk findings",
        [
            f"[{finding.severity}] {finding.code}: {finding.message} "
            f"Observed={finding.observed}; threshold={finding.threshold}; "
            f"evidence={', '.join(finding.evidence_refs)}"
            for finding in report.risk_findings
        ]
        or report.risks,
    )
    section("Missing inputs", report.missing_data)
    if report.assessment:
        section(
            "Evidence-linked assessment",
            [
                f"{item.statement} Evidence: {', '.join(item.evidence_refs)}"
                for item in report.assessment.observations
            ],
        )
        section("Review questions", report.assessment.review_questions)
        section("Limitations", report.assessment.limitations)
    lines.extend(
        [
            "",
            (
                "Ratios and weights are fractions (0.2 = 20%). "
                "Risk thresholds are research heuristics. Research only; no trading authorization."
            ),
            "",
        ]
    )
    return "\n".join(lines)
