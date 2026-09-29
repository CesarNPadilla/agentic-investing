import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import AwareDatetime, SecretStr
from sqlalchemy.exc import SQLAlchemyError

from integrations.brokers.base import AccountNotFound, BrokerReader, BrokerUnavailable
from news.thesis_review import (
    NewsReviewInput,
    ThesisReviewRequest,
    news_to_reviews,
    scheduled_reviews,
)
from portfolio.intelligence import analyze_portfolio
from portfolio.models import Account, CashBalance, Position
from portfolio.reconciliation import reconcile
from portfolio.state import PortfolioState, Record, StateOrder, Transaction
from portfolio.storage import (
    AnalysisInput,
    PortfolioObservation,
    PortfolioStore,
    StoredThesis,
    ThesisInput,
)
from risk.evaluator import KillSwitch
from risk.policy import InvestmentPolicy
from risk.proposals import TradeProposal
from risk.workflow import StrategyValidation, review_proposal


class ProposalReviewInput(Record):
    opening_id: str
    proposal: TradeProposal
    kill_switch: KillSwitch
    validation: StrategyValidation | None = None


def broker_read_router(
    reader_factory: Callable[[], BrokerReader],
    token: SecretStr,
    store: PortfolioStore | None = None,
    policy: InvestmentPolicy | None = None,
):
    policy = policy or InvestmentPolicy()
    router = APIRouter(
        prefix="/broker",
        tags=["Read-only broker data"],
    )

    def authenticate(authorization: str | None = Header(default=None)):
        expected = "Bearer " + token.get_secret_value()
        if not authorization or not secrets.compare_digest(authorization, expected):
            raise HTTPException(401, "Invalid broker read credential")

    def get_reader() -> BrokerReader:
        try:
            return reader_factory()
        except (BrokerUnavailable, SQLAlchemyError):
            raise HTTPException(503, "Broker data unavailable") from None

    ReaderDependency = Annotated[BrokerReader, Depends(get_reader)]

    def call(function, *args):
        try:
            return function(*args)
        except AccountNotFound:
            raise HTTPException(404, "Broker account not found") from None
        except (BrokerUnavailable, SQLAlchemyError):
            raise HTTPException(503, "Broker data unavailable") from None

    auth = [Depends(authenticate)]

    @router.get("/accounts", response_model=list[Account], dependencies=auth)
    def accounts(reader: ReaderDependency):
        return call(reader.get_accounts)

    @router.get(
        "/accounts/{account_id}/cash",
        response_model=list[CashBalance],
        dependencies=auth,
    )
    def cash(account_id: str, reader: ReaderDependency):
        return call(reader.get_cash, account_id)

    @router.get(
        "/accounts/{account_id}/positions",
        response_model=list[Position],
        dependencies=auth,
    )
    def positions(account_id: str, reader: ReaderDependency):
        return call(reader.get_positions, account_id)

    def method(reader, name):
        function = getattr(reader, name, None)
        if not callable(function):
            raise HTTPException(503, "Broker reader does not support complete portfolio reads")
        return function

    def storage():
        if store is None:
            raise HTTPException(503, "Portfolio storage unavailable")
        return store

    def observation(observation_id):
        result = call(storage().get, observation_id)
        if result is None:
            raise HTTPException(404, "Portfolio observation not found")
        return result

    @router.get(
        "/accounts/{account_id}/open-orders", response_model=list[StateOrder], dependencies=auth
    )
    def open_orders(account_id: str, reader: ReaderDependency):
        return call(method(reader, "get_open_orders"), account_id)

    @router.get(
        "/accounts/{account_id}/transactions", response_model=list[Transaction], dependencies=auth
    )
    def transactions(
        account_id: str, start: AwareDatetime, end: AwareDatetime, reader: ReaderDependency
    ):
        if start >= end:
            raise HTTPException(422, "History start must precede end")
        return call(method(reader, "get_transactions"), account_id, start, end)

    @router.get("/portfolio", response_model=PortfolioObservation, dependencies=auth)
    def portfolio(
        history_start: AwareDatetime, reader: ReaderDependency, opening_id: str | None = None
    ):
        opening = observation(opening_id) if opening_id else None
        if opening and opening.state.as_of != history_start:
            raise HTTPException(422, "History must start at the opening snapshot cutoff")
        state = call(lambda: method(reader, "read_state")(history_start=history_start))
        theses = call(storage().initialize_theses, state)
        result = PortfolioObservation(
            policy=policy,
            theses=theses,
            opening_id=opening_id,
            state=state,
            intelligence=analyze_portfolio(state, policy, theses=theses),
            reconciliation=reconcile(opening.state, state) if opening else None,
        )
        call(storage().save, result)
        return result

    @router.get(
        "/portfolio/{observation_id}", response_model=PortfolioObservation, dependencies=auth
    )
    def get_portfolio(observation_id: str):
        return observation(observation_id)

    @router.post(
        "/portfolio/{observation_id}/analysis",
        response_model=PortfolioObservation,
        dependencies=auth,
    )
    def analyze(observation_id: str, request: AnalysisInput):
        previous = observation(observation_id)
        request = request.resolve(previous)
        state = PortfolioState.model_validate(
            previous.state.model_dump()
            | {"experimental_attribution": request.experimental_attribution}
        )
        theses = call(storage().initialize_theses, state)
        intelligence = analyze_portfolio(
            state,
            policy,
            request.references,
            theses,
            request.correlations,
            request.performance_evidence,
        )
        if request.experimental_attribution and not intelligence.experimental_capital.valid:
            raise HTTPException(422, "Experimental attribution does not match broker inventory")
        result = PortfolioObservation(
            policy=policy,
            derived_from_id=previous.id,
            theses=theses,
            state=state,
            opening_id=previous.opening_id,
            reconciliation=previous.reconciliation,
            intelligence=intelligence,
            reference_data=request.references,
            correlation_evidence=request.correlations,
            performance_evidence=request.performance_evidence,
        )
        call(storage().save, result)
        return result

    @router.get(
        "/accounts/{account_id}/theses/{symbol}", response_model=StoredThesis, dependencies=auth
    )
    def get_thesis(account_id: str, symbol: str):
        result = call(storage().get_thesis, account_id, symbol.upper())
        if result is None:
            raise HTTPException(404, "Position thesis not found")
        return result

    @router.get(
        "/accounts/{account_id}/theses/{symbol}/history",
        response_model=tuple[StoredThesis, ...],
        dependencies=auth,
    )
    def thesis_history(
        account_id: str,
        symbol: str,
        after_revision: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
    ):
        return call(storage().thesis_history, account_id, symbol.upper(), after_revision, limit)

    @router.put(
        "/portfolio/{observation_id}/thesis", response_model=StoredThesis, dependencies=auth
    )
    def save_thesis(observation_id: str, request: ThesisInput):
        state = observation(observation_id).state
        if not any(
            p.account_id == request.thesis.account_id and p.symbol == request.thesis.symbol
            for p in state.portfolio_holdings
        ):
            raise HTTPException(422, "Thesis must reference a holding in this observation")
        try:
            return call(storage().save_thesis, request)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @router.post(
        "/portfolio/{observation_id}/news-review",
        response_model=tuple[ThesisReviewRequest, ...],
        dependencies=auth,
    )
    def news_review(observation_id: str, request: NewsReviewInput):
        state = observation(observation_id).state
        theses = call(storage().initialize_theses, state)
        try:
            requests = news_to_reviews(request, theses, now=datetime.now(UTC))
        except ValueError:
            raise HTTPException(422, "News review evidence is invalid") from None
        call(storage().save_review_requests, requests, request)
        return requests

    @router.get(
        "/portfolio/{observation_id}/review-queue",
        response_model=tuple[ThesisReviewRequest, ...],
        dependencies=auth,
    )
    def review_queue(observation_id: str):
        state = observation(observation_id).state
        theses = call(storage().initialize_theses, state)
        requests = scheduled_reviews(theses, now=datetime.now(UTC))
        call(storage().save_review_requests, requests)
        return call(storage().review_requests, state)

    @router.post("/portfolio/{observation_id}/proposal-review", dependencies=auth)
    def proposal_review(observation_id: str, request: ProposalReviewInput):
        closing = observation(observation_id)
        opening = observation(request.opening_id)
        stored = call(
            storage().get_thesis, request.proposal.trade.account_id, request.proposal.trade.symbol
        )
        thesis = stored.thesis if stored else None
        result = review_proposal(
            policy,
            opening.state,
            closing.state,
            request.proposal,
            request.kill_switch,
            thesis,
            now=datetime.now(UTC),
            validation=request.validation,
        )
        identifier = call(
            storage().save_risk_review,
            result,
            policy,
            opening.id,
            closing.id,
            thesis,
            request.validation,
            request.kill_switch,
        )
        return {"id": identifier, "review": result}

    @router.get("/proposal-reviews/{review_id}", dependencies=auth)
    def get_proposal_review(review_id: str):
        result = call(storage().get_risk_review, review_id)
        if result is None:
            raise HTTPException(404, "Proposal review not found")
        return result

    return router
