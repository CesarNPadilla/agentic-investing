"""Treat publisher text as data; topic matching is not sentiment or verification."""

from datetime import datetime, timedelta
from typing import Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator

from market_data.models import Symbol


class Article(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1, max_length=200)
    headline: str = Field(min_length=1, max_length=2000)
    url: HttpUrl
    publisher: str = Field(min_length=1, max_length=200)
    published_at: AwareDatetime
    symbols: tuple[Symbol, ...] = Field(min_length=1, max_length=100)


class Catalyst(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    title: str = Field(min_length=1, max_length=500)
    category: Literal["earnings", "product", "regulatory", "corporate_action", "other"]
    event_at: AwareDatetime
    evidence_id: str = Field(min_length=1, max_length=200)
    certainty: Literal["confirmed", "estimated"] = "estimated"


class NewsEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    symbol: Symbol
    source: str = Field(min_length=1, max_length=200)
    retrieved_at: AwareDatetime
    window_start: AwareDatetime
    is_sample: bool = False
    articles: tuple[Article, ...] = Field(default=(), max_length=200)
    catalysts: tuple[Catalyst, ...] = Field(default=(), max_length=100)

    @model_validator(mode="after")
    def validate_evidence(self):
        if self.window_start > self.retrieved_at:
            raise ValueError("News window must start before retrieval")
        ids = [article.id for article in self.articles]
        if len(ids) != len(set(ids)):
            raise ValueError("Article IDs must be unique")
        for article in self.articles:
            if self.symbol not in article.symbols:
                raise ValueError("Article must reference the requested symbol")
            if not self.window_start <= article.published_at <= self.retrieved_at:
                raise ValueError("Article publication must fall within the supplied news window")
        if any(event.evidence_id not in ids for event in self.catalysts):
            raise ValueError("Every catalyst must reference a supplied article")
        return self


class NewsProvider(Protocol):
    def get_news(self, symbol: str) -> NewsEvidence: ...


class NewsAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence: NewsEvidence
    article_count: int
    recent_article_ids: list[str] = Field(default_factory=list)
    topics: dict[str, list[str]] = Field(default_factory=dict)
    upcoming_catalysts: list[Catalyst] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


TOPICS = {
    "earnings": ("earnings", "revenue", "guidance", "quarterly results"),
    "regulatory": ("regulator", "regulatory", "antitrust", "approval", "lawsuit"),
    "corporate_action": ("merger", "acquisition", "dividend", "buyback", "stock split"),
    "product": ("launch", "product", "release"),
}


def analyze(evidence: NewsEvidence, now: datetime) -> NewsAnalysis:
    result = NewsAnalysis(evidence=evidence, article_count=0)
    if evidence.retrieved_at > now:
        result.warnings.append("News evidence is future-dated; analysis omitted.")
        return result
    # Repeated URLs count once; cross-URL syndication is not detected.
    seen = set()
    for article in sorted(
        evidence.articles, key=lambda item: (item.published_at, item.id), reverse=True
    ):
        key = str(article.url).split("#", 1)[0]
        if key in seen:
            continue
        seen.add(key)
        result.article_count += 1
        if article.published_at >= now - timedelta(days=7):
            result.recent_article_ids.append(article.id)
        for topic, words in TOPICS.items():
            if any(word in article.headline.lower() for word in words):
                result.topics.setdefault(topic, []).append(article.id)
    seen_events = set()
    for event in sorted(evidence.catalysts, key=lambda item: item.event_at):
        key = (event.title.casefold(), event.event_at, event.category)
        if event.event_at >= now and key not in seen_events:
            result.upcoming_catalysts.append(event)
            seen_events.add(key)
    result.warnings.append(
        "Headlines and catalyst claims are unverified external evidence; keyword topics do not "
        "establish sentiment, financial impact, or independent corroboration."
    )
    if not result.recent_article_ids:
        result.warnings.append("No articles from the past seven days in supplied evidence.")
    if (now - evidence.retrieved_at).total_seconds() > 86400:
        result.warnings.append("News evidence was retrieved over 24 hours ago.")
    if evidence.is_sample:
        result.warnings.append("Synthetic news and catalysts; not investment evidence.")
    return result
