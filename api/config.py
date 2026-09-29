from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AIL_", env_file=".env", extra="ignore")
    mode: Literal["research"] = "research"
    market_provider: Literal["sample", "alpaca"] = "sample"
    alpaca_api_key: SecretStr = SecretStr("")
    alpaca_api_secret: SecretStr = SecretStr("")
    llm_provider: Literal["disabled"] = "disabled"
    database_url: str = "sqlite:///./research.db"
    trading_enabled: bool = False
    trading_agent_token: SecretStr = SecretStr("")
    trading_approval_token: SecretStr = SecretStr("")
    broker_read_enabled: bool = False
    broker_read_token: SecretStr = SecretStr("")
    webull_production_env_file: Path | None = None
    investment_policy_file: Path | None = None

    @model_validator(mode="after")
    def require_provider_credentials(self):
        if self.trading_enabled:
            agent = self.trading_agent_token.get_secret_value()
            human = self.trading_approval_token.get_secret_value()
            if len(agent.strip()) < 32 or len(human.strip()) < 32 or agent == human:
                raise ValueError(
                    "Trading requires distinct agent and human tokens of 32+ characters"
                )
        if self.market_provider == "alpaca" and not (
            self.alpaca_api_key.get_secret_value().strip()
            and self.alpaca_api_secret.get_secret_value().strip()
        ):
            raise ValueError("Alpaca requires an API key and secret")
        if self.broker_read_enabled:
            broker_token = self.broker_read_token.get_secret_value()
            trading_tokens = {
                self.trading_agent_token.get_secret_value(),
                self.trading_approval_token.get_secret_value(),
            }
            if len(broker_token.strip()) < 32 or broker_token in trading_tokens:
                raise ValueError(
                    "Broker reads require a distinct bearer token of at least 32 characters"
                )
        return self
