"""Exact NY-midnight paper equity from documented continuous portfolio history."""

import hashlib
import json
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx

from market_data.base import ProviderUnavailable
from risk.paper_daily_loss import BoundaryEvidence

NY = ZoneInfo("America/New_York")


class AlpacaPaperBoundaryReader:
    def __init__(self, key, secret, *, account_reader, transport=None, clock=None):
        if not key or not secret:
            raise ValueError("Credentials required")
        self._headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self.account_reader = account_reader
        self.transport = transport
        self.clock = clock or (lambda: datetime.now(UTC))

    def read(self, day):
        start = datetime.combine(day, time(0), NY)
        end = start + timedelta(minutes=1)
        instant = self.clock()
        if instant.tzinfo is None or end > instant:
            raise ValueError("Completed boundary reporting interval required")
        try:
            before = self.account_reader.observe()
            with httpx.Client(
                timeout=15, transport=self.transport, follow_redirects=False
            ) as client:
                response = client.get(
                    "https://paper-api.alpaca.markets/v2/account/portfolio/history",
                    headers=self._headers,
                    params={
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                        "timeframe": "1Min",
                        "intraday_reporting": "continuous",
                        "pnl_reset": "no_reset",
                        "cashflow_types": "ALL",
                    },
                )
            if response.status_code != 200:
                raise ValueError("Boundary source unavailable")
            after = self.account_reader.observe()
            if (
                before.account_binding_sha256 != after.account_binding_sha256
                or not before.account_unblocked
                or not after.account_unblocked
            ):
                raise ValueError("Boundary account binding unqualified")
            row = json.loads(response.content, parse_float=str)
            stamps, equities = row["timestamp"], row["equity"]
            if (
                not isinstance(stamps, list)
                or not isinstance(equities, list)
                or len(stamps) != len(equities)
                or not stamps
                or any(type(t) is not int for t in stamps)
                or len(set(stamps)) != len(stamps)
                or stamps != sorted(stamps)
                or any(not start.timestamp() <= t <= end.timestamp() for t in stamps)
            ):
                raise ValueError("Malformed boundary series")
            exact = stamps.index(int(start.timestamp()))
            return BoundaryEvidence(
                account_binding=after.account_binding_sha256,
                source_digest=hashlib.sha256(response.content).hexdigest(),
                source_description="Alpaca paper portfolio history: 1Min continuous ALL cashflows",
                source_kind="ALPACA_PAPER_CONTINUOUS_HISTORY",
                as_of=start,
                equity=equities[exact],
            )
        except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError) as exc:
            raise ProviderUnavailable("Paper midnight equity evidence unavailable") from exc
