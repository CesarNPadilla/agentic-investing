"""Bounded read-only paper activities acquisition; coverage is not settlement proof."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict

from market_data.base import ProviderUnavailable


class PaperActivities(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    after: AwareDatetime
    until: AwareDatetime
    received_at: AwareDatetime
    rows: tuple[dict, ...]
    page_digests: tuple[str, ...]
    pagination_exhausted: bool
    execution_available: Literal[False] = False


class AlpacaPaperActivityReader:
    def __init__(self, key, secret, *, transport=None, clock=None):
        if not key or not secret:
            raise ValueError("Credentials required")
        self._headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))

    def read(self, *, after, until):
        if any(t.tzinfo is None or t.utcoffset() is None for t in (after, until)) or after >= until:
            raise ValueError("Aware ordered acquisition interval required")
        if until > self._clock():
            raise ValueError("Future acquisition cutoff")
        params = {
            "after": after.isoformat(),
            "until": until.isoformat(),
            "direction": "asc",
            "page_size": 100,
        }
        rows, digests, ids = [], [], set()
        try:
            with httpx.Client(
                timeout=15, transport=self._transport, follow_redirects=False
            ) as client:
                for _ in range(100):
                    response = client.get(
                        "https://paper-api.alpaca.markets/v2/account/activities",
                        headers=self._headers,
                        params=params,
                    )
                    if response.status_code != 200:
                        raise ValueError("Activity read failed")
                    page = json.loads(response.content)
                    if not isinstance(page, list) or len(page) > 100:
                        raise ValueError("Malformed page")
                    digests.append(hashlib.sha256(response.content).hexdigest())
                    for row in page:
                        if (
                            not isinstance(row, dict)
                            or not isinstance(row.get("id"), str)
                            or not row["id"]
                        ):
                            raise ValueError("Missing activity identity")
                        if row["id"] in ids:
                            raise ValueError("Duplicate or repeated activity page")
                        ids.add(row["id"])
                        rows.append(row)
                    if len(page) < 100:
                        return PaperActivities(
                            after=after,
                            until=until,
                            received_at=self._clock(),
                            rows=tuple(rows),
                            page_digests=tuple(digests),
                            pagination_exhausted=True,
                        )
                    params["page_token"] = page[-1]["id"]
            raise ValueError("Activity page limit exceeded")
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            raise ProviderUnavailable("Paper activity acquisition unavailable or invalid") from None
