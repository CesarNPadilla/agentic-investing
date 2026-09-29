"""Untrusted news can request thesis review only. No strategy/broker capability."""

import calendar
import hashlib
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime

from news.analysis import Article
from portfolio.state import Record
from portfolio.theses import PositionThesis

ReviewTrigger = Literal[
    "earnings",
    "guidance",
    "regulatory",
    "management",
    "acquisition_divestiture",
    "competition",
    "product",
    "macro",
    "valuation",
    "invalidation",
    "concentration",
    "quarterly_review",
    "baseline_review",
]


class ThesisReviewRequest(Record):
    request_id: str
    account_id: str
    symbol: str
    trigger: ReviewTrigger
    requested_at: AwareDatetime
    evidence_reference: str
    action: Literal["THESIS_REVIEW"] = "THESIS_REVIEW"
    execution_available: Literal[False] = False


class NewsReviewInput(Record):
    article: Article
    trigger: ReviewTrigger
    material: bool


def review_request(thesis, trigger, evidence, now):
    identity = f"{thesis.account_id}\0{thesis.symbol}\0{trigger}\0{evidence}"
    return ThesisReviewRequest(
        request_id=hashlib.sha256(identity.encode()).hexdigest(),
        account_id=thesis.account_id,
        symbol=thesis.symbol,
        trigger=trigger,
        requested_at=now,
        evidence_reference=evidence,
    )


def news_to_reviews(news: NewsReviewInput, theses: tuple[PositionThesis, ...], *, now: datetime):
    if now.tzinfo is None:
        raise ValueError("Review time must be timezone-aware")
    if news.article.published_at > now:
        raise ValueError("Future news cannot trigger review")
    if not news.material:
        return ()
    # Publisher text is stored as evidence elsewhere, never interpreted as instructions.
    return tuple(
        review_request(t, news.trigger, news.article.id, now)
        for t in theses
        if t.symbol in news.article.symbols
    )


def add_months(value: datetime, months: int):
    index = value.year * 12 + value.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    return value.replace(
        year=year, month=month, day=min(value.day, calendar.monthrange(year, month)[1])
    )


def scheduled_reviews(theses: tuple[PositionThesis, ...], *, now: datetime):
    if now.tzinfo is None:
        raise ValueError("Review time must be timezone-aware")
    requests = []
    for thesis in theses:
        if thesis.classification != "STRATEGIC_LONG_TERM":
            continue
        if thesis.last_review_date is None:
            requests.append(
                review_request(thesis, "baseline_review", "missing-review-baseline", now)
            )
            continue
        due = add_months(thesis.last_review_date, 3)
        if thesis.next_scheduled_review is not None:
            due = min(due, thesis.next_scheduled_review)
        if now >= due:
            requests.append(review_request(thesis, "quarterly_review", due.isoformat(), now))
    return tuple(requests)
