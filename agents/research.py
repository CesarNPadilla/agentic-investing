from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from pydantic import TypeAdapter

from fundamentals.analysis import FundamentalProvider
from fundamentals.analysis import analyze as analyze_fundamentals
from market_data.base import MarketDataProvider, ProviderUnavailable
from market_data.models import Symbol
from news.analysis import NewsProvider
from news.analysis import analyze as analyze_news
from portfolio.exposure import analyze as analyze_portfolio
from reports.inputs import ResearchEvidence
from reports.models import ResearchReport
from reports.synthesis import finalize
from risk.research import quote_warnings
from technical.history import summarize


class ResearchOrchestrator:
    def __init__(
        self,
        market_data: MarketDataProvider,
        fundamentals: FundamentalProvider | None = None,
        news: NewsProvider | None = None,
    ):
        self.market_data = market_data
        self.fundamental_provider = fundamentals
        self.news_provider = news

    def research(self, symbol: str, evidence: ResearchEvidence | None = None) -> ResearchReport:
        symbol = TypeAdapter(Symbol).validate_python(symbol)
        evidence = evidence or ResearchEvidence()
        for supplied in (evidence.fundamentals, evidence.news, evidence.price_history):
            if supplied is not None and supplied.symbol != symbol:
                raise ValueError("Evidence symbol must match requested symbol")
        quote = self.market_data.get_quote(symbol)
        if quote.symbol != symbol:
            raise ValueError("Provider returned a quote for a different symbol")
        now = datetime.now(UTC)
        history = None
        technicals = None
        history_warnings = []
        analyses = {}
        evidence_warnings = []
        for name, supplied, provider, method, analyzer in (
            (
                "fundamentals",
                evidence.fundamentals,
                self.fundamental_provider,
                "get_fundamentals",
                analyze_fundamentals,
            ),
            ("news", evidence.news, self.news_provider, "get_news", analyze_news),
        ):
            try:
                data = supplied
                if data is None and provider is not None:
                    data = getattr(provider, method)(symbol)
                if data is not None:
                    if data.symbol != symbol:
                        raise ProviderUnavailable("Evidence symbol mismatch")
                    analyses[name] = analyzer(data, now)
                    evidence_warnings.extend(analyses[name].warnings)
            except ProviderUnavailable:
                evidence_warnings.append(
                    f"{name.capitalize()} provider unavailable; analysis omitted."
                )
        fundamentals = analyses.get("fundamentals")
        news = analyses.get("news")
        get_history = getattr(self.market_data, "get_history", None)
        if evidence.price_history is not None or get_history is not None:
            try:
                history = (
                    evidence.price_history
                    if evidence.price_history is not None
                    else get_history(symbol)
                )
                if history.symbol != symbol:
                    raise ProviderUnavailable("History symbol mismatch")
                cutoff = now.astimezone(ZoneInfo("America/New_York")).replace(
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                eligible = tuple(bar for bar in history.bars if bar.timestamp < cutoff)
                technicals = summarize(history.model_copy(update={"bars": eligible}))
                history_warnings.append(
                    "Daily bars may omit sessions; exchange-calendar completeness is unverified. "
                    "Indicators use observed closes, excluding today's New York session and future bars."
                )
                if len(eligible) != len(history.bars):
                    history_warnings.append(
                        "Current-session or future history bars excluded from indicators."
                    )
                if history.is_sample:
                    history_warnings.append(
                        "Synthetic price history; not actual market observations."
                    )
                if history.adjustment == "raw":
                    history_warnings.append(
                        "Unadjusted price history can distort indicators at corporate actions."
                    )
                elif history.adjustment == "split":
                    history_warnings.append(
                        "History is split-adjusted only; returns exclude cash dividends."
                    )
                if eligible and (now - eligible[-1].timestamp).days > 7:
                    history_warnings.append("Price history is over seven days old.")
            except ProviderUnavailable:
                history = None
                history_warnings.append("Price history unavailable; technical analysis omitted.")
        portfolio = (
            analyze_portfolio(evidence.portfolio, symbol, now) if evidence.portfolio else None
        )
        if portfolio:
            evidence_warnings.extend(portfolio.warnings)
        sample_flags = [quote.is_sample]
        sample_flags.extend(
            item.is_sample
            for item in (
                history,
                evidence.portfolio,
                fundamentals.evidence if fundamentals else None,
                news.evidence if news else None,
            )
            if item is not None
        )
        if len(set(sample_flags)) > 1:
            evidence_warnings.append(
                "Report combines synthetic and non-synthetic evidence; review each source."
            )
        return finalize(
            ResearchReport(
                analysis_version="research-v2",
                portfolio=portfolio,
                fundamentals=fundamentals,
                news=news,
                catalysts=[
                    f"{event.event_at.isoformat()}: {event.title} ({event.certainty}; "
                    f"evidence: {event.evidence_id})"
                    for event in news.upcoming_catalysts
                ]
                if news
                else [],
                price_history=history,
                technicals=technicals,
                technical_state=technicals.state if technicals else "unavailable",
                symbol=symbol,
                quote=quote,
                generated_at=now,
                summary="",  # Populated by deterministic synthesis below.
                risks=quote_warnings(quote, now)
                + history_warnings
                + evidence_warnings
                + (
                    ["IEX-only last trade; not a consolidated market quote or executable price."]
                    if quote.source == "alpaca-iex-last-trade"
                    else []
                ),
                missing_data=[
                    *(
                        ["fundamentals"]
                        if not fundamentals
                        else [f"fundamentals.{name}" for name in fundamentals.missing_metrics]
                    ),
                    *(["price_history"] if not technicals else []),
                    *(
                        ["technicals"]
                        if not technicals
                        else [f"technicals.{name}" for name in technicals.missing_indicators]
                    ),
                    *(["news"] if not news or news.evidence.retrieved_at > now else []),
                    *(["catalysts"] if not news or not news.upcoming_catalysts else []),
                    *(
                        ["portfolio_exposure"]
                        if not portfolio or portfolio.state == "unavailable"
                        else []
                    ),
                    "investment_thesis",
                ],
            )
        )
