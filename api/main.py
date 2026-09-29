import secrets
from contextlib import asynccontextmanager
from pathlib import Path as FilePath
from typing import Annotated, Literal
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Path
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from agents.research import ResearchOrchestrator
from api.broker import broker_read_router
from api.config import Settings
from database.repository import SQLReportRepository
from integrations.brokers.base import BrokerReader, BrokerUnavailable
from market_data.alpaca import AlpacaMarketDataProvider
from market_data.base import MarketDataProvider, ProviderUnavailable, SymbolNotFound
from market_data.models import Symbol
from market_data.sample import SampleMarketDataProvider
from portfolio.storage import PortfolioStore
from reports.inputs import ResearchEvidence
from reports.markdown import render_markdown
from reports.models import ResearchReport
from risk.policy import InvestmentPolicy, load_investment_policy
from simulation.engine import evaluate
from simulation.models import PaperAdvance, SimulationInput, SimulationRun
from trading.api import trading_router
from trading.service import TradingService


def create_app(
    settings: Settings | None = None,
    market_data: MarketDataProvider | None = None,
    broker_reader: BrokerReader | None = None,
    investment_policy: InvestmentPolicy | None = None,
) -> FastAPI:
    settings = settings or Settings()
    if investment_policy is not None and settings.investment_policy_file is not None:
        raise ValueError("Configure one investment policy source, not both file and injection")
    investment_policy = investment_policy or load_investment_policy(settings.investment_policy_file)
    repository = SQLReportRepository(settings.database_url)
    trading = TradingService(repository.engine) if settings.trading_enabled else None
    if market_data is None:
        market_data = (
            AlpacaMarketDataProvider(
                settings.alpaca_api_key.get_secret_value(),
                settings.alpaca_api_secret.get_secret_value(),
            )
            if settings.market_provider == "alpaca"
            else SampleMarketDataProvider()
        )
    orchestrator = ResearchOrchestrator(market_data)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            repository.initialize()
            if trading:
                trading.initialize()
            yield
        finally:
            repository.close()

    app = FastAPI(title="Agentic Investing Research", version="0.1.0", lifespan=lifespan)
    if trading:
        app.include_router(trading_router(trading, settings))
    if settings.broker_read_enabled:
        reader_cache = [broker_reader]

        def get_production_reader() -> BrokerReader:
            if reader_cache[0] is not None:
                return reader_cache[0]
            try:
                import os

                from integrations.brokers.webull_production import (
                    WebullProductionBrokerReader,
                    WebullProductionCredentials,
                    WebullProductionError,
                    WebullProductionReadOnly,
                )

                env_file = settings.webull_production_env_file
                if env_file is None:
                    local_app_data = os.environ.get("LOCALAPPDATA")
                    if not local_app_data:
                        raise BrokerUnavailable("Production credential path is unavailable")
                    env_file = FilePath(local_app_data) / "AgenticInvesting" / "webull.env"
                credentials = WebullProductionCredentials.from_env_file(env_file)
                access = WebullProductionReadOnly(
                    credentials.app_key.get_secret_value(),
                    credentials.app_secret.get_secret_value(),
                )
                reader_cache[0] = WebullProductionBrokerReader(access)
            except WebullProductionError:
                raise BrokerUnavailable("Production broker client unavailable") from None
            return reader_cache[0]

        app.include_router(
            broker_read_router(
                get_production_reader,
                settings.broker_read_token,
                PortfolioStore(repository.engine),
                investment_policy,
            )
        )

    def store_simulation(inputs, mode):
        run = evaluate(inputs, mode)
        try:
            repository.save_simulation(run)
        except SQLAlchemyError:
            raise HTTPException(503, "Simulation storage unavailable") from None
        return run

    @app.post("/backtests", response_model=SimulationRun, status_code=201)
    def backtest(inputs: SimulationInput):
        return store_simulation(inputs, "backtest")

    @app.post("/paper-sessions", response_model=SimulationRun, status_code=201)
    def paper_session(inputs: SimulationInput):
        if len(inputs.history.bars) != 1:
            raise HTTPException(422, "Start paper sessions with exactly one paired observation")
        return store_simulation(inputs, "paper")

    @app.get("/simulations/{run_id}", response_model=SimulationRun)
    def get_simulation(run_id: UUID):
        try:
            run = repository.get_simulation(run_id)
        except SQLAlchemyError:
            raise HTTPException(503, "Simulation storage unavailable") from None
        if run is None:
            raise HTTPException(404, "Simulation not found")
        return run

    @app.post("/paper-sessions/{run_id}/bars", response_model=SimulationRun)
    def advance_paper(run_id: UUID, request: PaperAdvance):
        previous = get_simulation(run_id)
        if previous.mode != "paper":
            raise HTTPException(409, "Only paper sessions accept new bars")
        if previous.revision != request.expected_revision:
            raise HTTPException(409, "Revision conflict; reload session before advancing")
        data = previous.inputs.model_dump(mode="json")
        data["history"]["bars"].append(request.bar.model_dump(mode="json"))
        data["benchmark"]["bars"].append(request.benchmark_bar.model_dump(mode="json"))
        try:
            inputs = SimulationInput.model_validate(data)
        except ValidationError:
            raise HTTPException(
                422, "Bars must be aligned, chronological, completed, and within 5000"
            ) from None
        run = evaluate(inputs, "paper")
        run.id, run.created_at = previous.id, previous.created_at
        run.revision = previous.revision + 1
        try:
            if not repository.save_simulation(run, request.expected_revision):
                raise HTTPException(409, "Revision conflict; reload session before advancing")
        except SQLAlchemyError:
            raise HTTPException(503, "Simulation storage unavailable") from None
        return run

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "mode": settings.mode,
            "trading_enabled": settings.trading_enabled,
            "broker_read_enabled": settings.broker_read_enabled,
            "execution_broker": "synthetic" if trading else None,
            "live_trading_enabled": False,
        }

    @app.get("/ready")
    def ready():
        try:
            repository.ready()
        except SQLAlchemyError:
            raise HTTPException(503, "Report storage unavailable") from None
        return {"status": "ready"}

    @app.post("/research/{symbol}", response_model=ResearchReport, status_code=201)
    def research(
        symbol: Annotated[Symbol, Path()],
        evidence: ResearchEvidence | None = None,
        authorization: str | None = Header(default=None),
    ):
        if not investment_policy.may_research(symbol):
            if (
                not settings.broker_read_enabled
                or not authorization
                or not secrets.compare_digest(
                    authorization, "Bearer " + settings.broker_read_token.get_secret_value()
                )
            ):
                raise HTTPException(
                    403, "Research requires universe permission or authenticated holdings"
                )
            try:
                reader = get_production_reader()
                holdings = [
                    p for a in reader.get_accounts() for p in reader.get_positions(a.account_id)
                ]
            except BrokerUnavailable:
                raise HTTPException(503, "Holdings unavailable for research permission") from None
            if not investment_policy.may_research(symbol, holdings):
                raise HTTPException(403, "Security is outside the research universe and portfolio")
        if evidence and any(
            item is not None and item.symbol != symbol
            for item in (evidence.fundamentals, evidence.news, evidence.price_history)
        ):
            raise HTTPException(422, "Evidence symbol must match requested symbol")
        try:
            report = orchestrator.research(symbol, evidence)
            repository.save(report)
            return report
        except SymbolNotFound:
            raise HTTPException(404, "Symbol unavailable from configured provider") from None
        except ProviderUnavailable:
            raise HTTPException(503, "Market data provider unavailable") from None
        except SQLAlchemyError:
            raise HTTPException(503, "Report storage unavailable") from None

    @app.get("/reports/{report_id}", response_model=ResearchReport)
    def get_report(report_id: UUID, format: Literal["json", "markdown"] = "json"):
        try:
            report = repository.get(report_id)
        except SQLAlchemyError:
            raise HTTPException(503, "Report storage unavailable") from None
        if report is None:
            raise HTTPException(404, "Report not found")
        if format == "markdown":
            return Response(
                render_markdown(report),
                media_type="text/markdown",
                headers={"Content-Disposition": f'attachment; filename="research-{report.id}.md"'},
            )
        return report

    return app


app = create_app()
