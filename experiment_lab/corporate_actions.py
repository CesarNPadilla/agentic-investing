"""Corporate actions remain separate from raw bars and fail closed on vintage."""

import hashlib
import json
from datetime import UTC, date, datetime

import httpx

from experiment_lab.historical_records import CorporateAction
from experiment_lab.knowledge_boundary import HistoricalKnowledgeBoundary, KnowledgeObservation


def normalize_alpaca_action(row: dict, retrieved_at: datetime) -> CorporateAction:
    """Do not substitute declaration/ex/process dates for API availability."""
    raw = json.dumps(row, sort_keys=True, separators=(",", ":"), default=str).encode()

    def day(name):
        value = row.get(name)
        return date.fromisoformat(value) if value else None

    announced = row.get("created_at")
    created_at = datetime.fromisoformat(announced) if announced else None
    if created_at is not None and created_at.tzinfo is None:
        created_at = None
    return CorporateAction(
        action_type=str(row.get("type") or "UNKNOWN"),
        symbol=str(row.get("symbol") or "UNKNOWN"),
        ex_date=day("ex_date"), record_date=day("record_date"),
        payable_date=day("payable_date"), process_date=day("process_date"),
        announced_at=created_at,
        source="Alpaca corporate actions", retrieved_at=retrieved_at,
        source_digest=hashlib.sha256(raw).hexdigest(),
        availability_confidence="UNVERIFIED_PROVIDER_CREATION_TIME",
    )


def action_known(action: CorporateAction, at: datetime,
                 boundary: HistoricalKnowledgeBoundary) -> bool:
    return boundary.require(KnowledgeObservation(
        "corporate_action", action.source_digest, action.announced_at,
        revision_proven=False,
    ), at)


class AlpacaCorporateActionProvider:
    def __init__(self, api_key: str, api_secret: str, *, transport=None):
        if not api_key or not api_secret:
            raise ValueError("Alpaca credentials required")
        self._headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_secret}
        self._transport = transport

    def actions(self, symbols: tuple[str, ...], start: date, end: date) -> tuple[CorporateAction, ...]:
        if not symbols or start >= end or end > date(2025, 12, 31):
            raise ValueError("Development/validation action range and symbols required")
        params = {"symbols": ",".join(symbols), "start": start.isoformat(),
                  "end": end.isoformat(), "data_quality": "all", "limit": 1000}
        actions, seen_tokens = [], set()
        with httpx.Client(timeout=20, transport=self._transport) as client:
            while True:
                try:
                    response = client.get("https://data.alpaca.markets/v1/corporate-actions",
                                          headers=self._headers, params=params)
                    if response.status_code != 200:
                        raise ValueError(f"HTTP {response.status_code}")
                    payload = response.json()
                except (httpx.HTTPError, ValueError) as exc:
                    reason = str(exc) if str(exc).startswith("HTTP ") else "unavailable"
                    raise ValueError(f"Alpaca corporate actions {reason}") from None
                retrieved_at = datetime.now(UTC)
                grouped = payload.get("corporate_actions")
                if not isinstance(grouped, dict):
                    raise TypeError("Invalid corporate-action response")
                for key, rows in grouped.items():
                    if not isinstance(rows, list):
                        raise TypeError("Invalid corporate-action event list")
                    for row in rows:
                        if isinstance(row, dict):
                            actions.append(normalize_alpaca_action(
                                {"type": row.get("type") or key, **row}, retrieved_at,
                            ))
                token = payload.get("next_page_token")
                if not token:
                    break
                if not isinstance(token, str) or token in seen_tokens:
                    raise ValueError("Invalid corporate-action pagination")
                seen_tokens.add(token)
                params["page_token"] = token
        return tuple(actions)
