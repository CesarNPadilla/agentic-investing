"""Bounded report synthesis. No network, model calls, or external-text instructions."""

from reports.assessment import ResearchAssessment, ResearchObservation
from reports.models import ResearchReport
from risk.analysis import identify


def finalize(report: ResearchReport) -> ResearchReport:
    observations = []

    def add(direction, statement, *refs):
        observations.append(
            ResearchObservation(
                direction=direction,
                statement=statement,
                evidence_refs=list(refs),
            )
        )

    fundamental = report.fundamentals
    if fundamental:
        if fundamental.revenue_growth is not None:
            value = fundamental.revenue_growth
            add(
                "supporting" if value > 0 else "counter" if value < 0 else "neutral",
                f"Supplied comparable periods show revenue growth of {value:.2%}.",
                "/fundamentals/revenue_growth",
            )
        if fundamental.net_margin is not None:
            value = fundamental.net_margin
            add(
                "supporting" if value > 0 else "counter" if value < 0 else "neutral",
                f"Supplied financial period has a net margin of {value:.2%}.",
                "/fundamentals/net_margin",
            )
        if fundamental.free_cash_flow is not None:
            value = fundamental.free_cash_flow
            add(
                "supporting" if value > 0 else "counter" if value < 0 else "neutral",
                f"Supplied period free cash flow is {value:,.2f} {fundamental.evidence.currency}.",
                "/fundamentals/free_cash_flow",
            )
    technical = report.technicals
    if technical:
        if technical.sma20 is not None and technical.sma50 is not None:
            direction = (
                "supporting"
                if technical.sma20 > technical.sma50
                else "counter"
                if technical.sma20 < technical.sma50
                else "neutral"
            )
            add(
                direction,
                f"Historical 20-bar SMA is {technical.sma20:.4f}; "
                f"50-bar SMA is {technical.sma50:.4f}.",
                "/technicals/sma20",
                "/technicals/sma50",
            )
        if technical.return_20 is not None:
            add(
                "neutral",
                f"The last 20 observed return intervals changed price by "
                f"{technical.return_20:.2%}.",
                "/technicals/return_20",
            )
    if report.portfolio and report.portfolio.researched_symbol_exposure is not None:
        exposure = report.portfolio.researched_symbol_exposure
        if exposure.gross_weight is not None:
            add(
                "neutral",
                f"{report.symbol} gross exposure is {exposure.gross_weight:.2%} "
                "of supplied portfolio equity.",
                "/portfolio/researched_symbol_exposure/gross_weight",
            )
    if report.news and report.news.evidence.retrieved_at <= report.generated_at:
        add(
            "neutral",
            f"Supplied news contains {report.news.article_count} unique URLs and "
            f"{len(report.news.upcoming_catalysts)} upcoming event claims.",
            "/news/article_count",
            "/news/upcoming_catalysts",
        )
    report.bull_case = [item.statement for item in observations if item.direction == "supporting"]
    report.bear_case = [item.statement for item in observations if item.direction == "counter"]
    report.risk_findings = identify(report, report.risk_policy)
    supporting, counter = len(report.bull_case), len(report.bear_case)
    report.assessment = ResearchAssessment(
        conclusion=(
            f"Available evidence yields {supporting} supporting and {counter} counter "
            "observations. These are descriptive research inputs, not a valuation or rating."
        ),
        observations=observations,
        review_questions=[
            "Do the latest filings confirm the reported growth, margins, and cash flow?",
            "Are upcoming event dates corroborated by primary company disclosures?",
            "Is the portfolio import complete, current, and appropriate for the investor's limits?",
            "What valuation assumptions and business risks would invalidate the investment thesis?",
        ],
        limitations=list(
            dict.fromkeys(
                [
                    "No fair value, price target, personalized suitability, or trade recommendation is computed.",
                    "Observations may use stale or synthetic evidence; review the accompanying data warnings.",
                    "Technical measures share price inputs and are not independent confirmations.",
                    "Risk thresholds are research heuristics; no finding does not establish safety.",
                    *report.risks,
                ]
            )
        ),
    )
    report.summary = (
        f"{report.symbol}: "
        f"{len(observations)} evidence-linked observations; {len(report.risk_findings)} risk/data "
        f"findings; {len(report.missing_data)} missing inputs. " + report.assessment.conclusion
    )
    return report
