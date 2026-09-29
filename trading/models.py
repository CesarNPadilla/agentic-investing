from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from market_data.models import Symbol


class ProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    account_id: Literal["synthetic-phase4"] = "synthetic-phase4"
    symbol: Symbol
    side: Literal["buy", "sell"]
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=6, allow_inf_nan=False)
    limit_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2, allow_inf_nan=False)
    order_type: Literal["limit"] = "limit"
    time_in_force: Literal["day"] = "day"
    rationale: str = Field(min_length=1, max_length=2000)
    strategy: str = Field(min_length=1, max_length=100)
    request_id: str = Field(min_length=1, max_length=100)


class ApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class KillSwitchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


class AutomationPolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    strategy: Literal["buy_and_hold", "sma"]
    strategy_version: Literal["1"] = "1"
    fast: int = Field(default=20, ge=1, le=499)
    slow: int = Field(default=50, ge=2, le=500)
    max_order_notional: Decimal = Field(
        default=Decimal(1000), gt=0, le=1000, allow_inf_nan=False
    )
    max_position_value: Decimal = Field(
        default=Decimal(2500), gt=0, le=2500, allow_inf_nan=False
    )
    max_portfolio_exposure: Decimal = Field(
        default=Decimal(5000), gt=0, le=5000, allow_inf_nan=False
    )
    max_daily_loss: Decimal = Field(default=Decimal(100), gt=0, le=100, allow_inf_nan=False)
    allowed_symbols: list[Symbol] = Field(default_factory=lambda: ["AAPL", "MSFT", "SPY"])
    allowed_order_type: Literal["limit"] = "limit"
    time_in_force: Literal["day"] = "day"
    trading_session: Literal["us_regular"] = "us_regular"
    kill_switch_required: Literal[True] = True
    audit_required: Literal[True] = True

    @model_validator(mode="after")
    def supported_symbols(self):
        if self.strategy == "sma" and self.fast >= self.slow:
            raise ValueError("SMA fast window must be smaller than slow window")
        if not self.allowed_symbols or len(set(self.allowed_symbols)) != len(self.allowed_symbols):
            raise ValueError("Allowed symbols must be nonempty and unique")
        if not set(self.allowed_symbols).issubset({"AAPL", "MSFT", "SPY"}):
            raise ValueError("Automation symbols must be within the server allowlist")
        return self


class AutomationQualificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    backtest_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    paper_run_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
