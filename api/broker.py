import secrets
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import AwareDatetime, SecretStr
from sqlalchemy.exc import SQLAlchemyError

from integrations.brokers.base import AccountNotFound, BrokerReader, BrokerUnavailable
from portfolio.intelligence import analyze_portfolio
from portfolio.models import Account, CashBalance, Position
from portfolio.reconciliation import reconcile
from portfolio.state import PortfolioState, StateOrder, Transaction
from portfolio.storage import (
    AnalysisInput,
    PortfolioObservation,
    PortfolioStore,
    StoredThesis,
    ThesisInput,
)
from risk.policy import InvestmentPolicy


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
        result = PortfolioObservation(
            opening_id=opening_id,
            state=state,
            intelligence=analyze_portfolio(state, policy),
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
        state = PortfolioState.model_validate(
            previous.state.model_dump()
            | {"experimental_attribution": request.experimental_attribution}
        )
        intelligence = analyze_portfolio(state, policy, request.references)
        if request.experimental_attribution and not intelligence.experimental_capital.valid:
            raise HTTPException(422, "Experimental attribution does not match broker inventory")
        result = PortfolioObservation(
            state=state,
            opening_id=previous.opening_id,
            reconciliation=previous.reconciliation,
            intelligence=intelligence,
            reference_data=request.references,
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

    return router
