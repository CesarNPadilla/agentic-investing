"""Read-only FMP fundamentals candidate. Never asserts unproven PIT revisions."""

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from experiment_lab.historical_records import HistoricalStatement

FMP_BASE = "https://financialmodelingprep.com/stable"
STATEMENT_ENDPOINTS = {
    "income": "income-statement",
    "balance": "balance-sheet-statement",
    "cash_flow": "cash-flow-statement",
}


def load_fmp_credential(path: Path) -> str:
    """Load an external env file at runtime, without retaining or printing its path/value."""
    if not path.is_file():
        raise ValueError("External FMP credential unavailable")
    values = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if separator and key.strip() == "FMP_API_KEY":
            values[key.strip()] = value.strip().strip('"').strip("'")
    credential = values.get("FMP_API_KEY", "")
    if not credential:
        raise ValueError("External FMP credential unavailable")
    return credential


def normalize_statement(row: dict, statement_type: str, retrieved_at: datetime) -> HistoricalStatement:
    """Preserve missing or timezone-less acceptance; never infer it from period end."""
    accepted = row.get("acceptedDate")
    accepted_at = None
    if isinstance(accepted, str) and accepted:
        parsed = datetime.fromisoformat(accepted)
        if parsed.tzinfo is not None:
            accepted_at = parsed.astimezone(UTC)
    normalized = {}
    for key, value in row.items():
        if (key in {"revenue", "netIncome", "freeCashFlow", "totalDebt",
                    "cashAndCashEquivalents", "ebitda", "grossProfitRatio",
                    "operatingIncomeRatio", "netIncomeRatio", "returnOnEquity",
                    "returnOnAssets", "operatingCashFlow", "capitalExpenditure"}
                and value is not None and not isinstance(value, bool)):
            normalized[key] = str(value)
    raw = json.dumps(row, sort_keys=True, separators=(",", ":"), default=str).encode()
    filing = row.get("filingDate")
    return HistoricalStatement(
        symbol=row["symbol"], fiscal_period=str(row.get("period") or "UNAVAILABLE"),
        period_end=date.fromisoformat(row["date"]),
        filing_date=date.fromisoformat(filing) if filing else None,
        accepted_at=accepted_at, retrieved_at=retrieved_at, source="FMP",
        raw_payload_digest=hashlib.sha256(raw).hexdigest(),
        normalized_values=normalized, currency=row.get("reportedCurrency"),
        statement_type=statement_type,
        amendment_indicator=(str(row["form"]) if row.get("form") else None),
        revision_proven=False,
        source_reference=(str(row["cik"]) if row.get("cik") else None),
        provider_metadata={"accepted_timestamp_raw_present": bool(accepted),
                           "accepted_timezone_explicit": accepted_at is not None},
    )


class FmpHistoricalFundamentalProvider:
    def __init__(self, credential: str, *, transport=None):
        if not credential:
            raise ValueError("FMP credential required")
        self._credential = credential
        self._transport = transport

    def statements(self, symbol: str, *, through: date) -> tuple[HistoricalStatement, ...]:
        if not symbol or through >= datetime.now(UTC).date():
            raise ValueError("Historical symbol and past cutoff required")
        retrieved_at = datetime.now(UTC)
        observations = []
        # FMP's ordinary statements are current-vintage records, not a proof of
        # what its API returned on a past date. Keep the cutoff before consumers.
        with httpx.Client(timeout=20, transport=self._transport) as client:
            for kind, endpoint in STATEMENT_ENDPOINTS.items():
                try:
                    response = client.get(
                        f"{FMP_BASE}/{endpoint}",
                        params={"symbol": symbol, "period": "quarter", "limit": 1000,
                                "apikey": self._credential},
                    )
                    if response.status_code != 200:
                        raise ValueError(f"FMP HTTP {response.status_code}")
                    payload = response.json()
                    if not isinstance(payload, list):
                        raise TypeError("Provider response unavailable")
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    reason = str(exc) if isinstance(exc, ValueError) and str(exc).startswith("FMP HTTP ") else "unavailable"
                    raise ValueError(f"FMP historical fundamentals {reason}") from None
                for row in payload:
                    if not isinstance(row, dict) or row.get("symbol") != symbol:
                        raise ValueError("FMP historical fundamentals unavailable")
                    # Do not normalize, persist, or expose reserved future records.
                    period_end = date.fromisoformat(row["date"])
                    if period_end <= through:
                        observations.append(normalize_statement(row, kind, retrieved_at))
        return tuple(observations)
