"""SEC EDGAR accession-scoped historical fundamentals candidate.

The current companyfacts API is a present-day aggregation. Accession matching
prevents a later amendment being silently substituted for an earlier filing,
but does not prove the API's earlier dissemination or post-acceptance vintage.
"""

import hashlib
import json
import time
from datetime import UTC, date, datetime

import httpx

from experiment_lab.historical_records import HistoricalStatement

SEC_BASE = "https://data.sec.gov"
FORMS = frozenset({"10-K", "10-Q", "10-K/A", "10-Q/A"})
TAGS = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
                "SalesRevenueNet"),
    "net_income": ("NetIncomeLoss",),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "capital_expenditure": ("PaymentsToAcquirePropertyPlantAndEquipment",
                            "PaymentsToAcquireProductiveAssets"),
    "gross_profit": ("GrossProfit",),
    "operating_income": ("OperatingIncomeLoss",),
    "cash": ("CashAndCashEquivalentsAtCarryingValue",),
    "debt_current": ("LongTermDebtCurrent", "CurrentPortionOfLongTermDebt"),
    "debt_noncurrent": ("LongTermDebtNoncurrent", "LongTermDebt"),
    "assets": ("Assets",),
    "equity": ("StockholdersEquity",),
}
INSTANT = frozenset({"cash", "debt_current", "debt_noncurrent", "assets", "equity"})


def _digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _filings(submissions: dict, through: date) -> dict[str, dict]:
    recent = submissions.get("filings", {}).get("recent", {})
    required = ("accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "form")
    if any(key not in recent for key in required):
        raise ValueError("SEC submissions schema incomplete")
    count = len(recent["accessionNumber"])
    if any(len(recent[key]) != count for key in required):
        raise ValueError("SEC submissions columns misaligned")
    selected = {}
    for index in range(count):
        form = recent["form"][index]
        if form not in FORMS:
            continue
        filed = date.fromisoformat(recent["filingDate"][index])
        report = date.fromisoformat(recent["reportDate"][index])
        accepted = datetime.fromisoformat(recent["acceptanceDateTime"][index])
        if accepted.tzinfo is None:
            # SEC's API normally supplies Z. Never guess from filing date.
            continue
        accepted = accepted.astimezone(UTC)
        if filed > through or report > through or accepted.date() > through:
            continue
        accession = recent["accessionNumber"][index]
        if accession in selected:
            raise ValueError("Duplicate SEC accession")
        selected[accession] = {
            "accession": accession, "form": form, "filed": filed,
            "report": report, "accepted": accepted,
        }
    return selected


def _extend_recent(submissions: dict, shard: dict) -> None:
    recent = submissions["filings"]["recent"]
    required = ("accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "form")
    if any(key not in shard for key in required):
        raise ValueError("SEC submissions shard incomplete")
    for key in required:
        recent[key].extend(shard[key])


def _choose_fact(facts: dict, accession: str, form: str, filed: date,
                 report: date, metric: str) -> tuple[dict, str] | None:
    for tag in TAGS[metric]:
        units = facts.get("us-gaap", {}).get(tag, {}).get("units", {})
        matches = []
        for fact in units.get("USD", []):
            if (fact.get("accn") != accession or fact.get("form") != form
                    or fact.get("filed") != filed.isoformat()
                    or fact.get("end") != report.isoformat()):
                continue
            start = fact.get("start")
            if metric in INSTANT:
                if start:
                    continue
            else:
                if not start:
                    continue
                duration = (report - date.fromisoformat(start)).days
                if form.startswith("10-K") and not 330 <= duration <= 380:
                    continue
                if form.startswith("10-Q") and not 60 <= duration <= 110:
                    continue
            matches.append(fact)
        if matches:
            # Conflicting values for the same accession/tag/period are ambiguous.
            if len({(m.get("start"), m.get("val")) for m in matches}) != 1:
                return None
            return matches[0], tag
    return None


def reconstruct_statements(symbol: str, cik: int, submissions: dict,
                           companyfacts: dict, through: date,
                           retrieved_at: datetime) -> tuple[HistoricalStatement, ...]:
    if int(submissions.get("cik", -1)) != cik or int(companyfacts.get("cik", -1)) != cik:
        raise ValueError("SEC CIK mismatch")
    selected = _filings(submissions, through)
    facts = companyfacts.get("facts", {})
    rows = []
    for accession, filing in selected.items():
        values, provenance = {}, {}
        for metric in TAGS:
            choice = _choose_fact(facts, accession, filing["form"], filing["filed"],
                                  filing["report"], metric)
            if choice is None:
                continue
            fact, tag = choice
            values[metric] = fact["val"]
            provenance[metric] = {
                "accession": accession, "taxonomy": "us-gaap", "tag": tag,
                "unit": "USD", "start": fact.get("start"), "end": fact["end"],
                "form": fact["form"], "filed": fact["filed"],
                "fact_digest": _digest(fact),
            }
        rows.append(HistoricalStatement(
            symbol=symbol, fiscal_period=("FY" if filing["form"].startswith("10-K")
                                          else "QUARTER"),
            period_end=filing["report"], filing_date=filing["filed"],
            accepted_at=filing["accepted"], retrieved_at=retrieved_at,
            source="SEC EDGAR submissions + companyfacts", raw_payload_digest=_digest(
                {"filing": filing, "values": values, "provenance": provenance}),
            normalized_values=values, currency="USD", statement_type=filing["form"],
            amendment_indicator=("AMENDMENT" if filing["form"].endswith("/A") else None),
            # Accession lineage is proven, but original dissemination/value
            # vintage is not attested by the current companyfacts response.
            revision_proven=False, source_reference=accession,
            provider_metadata={"cik": cik, "fact_provenance": provenance,
                               "submissions_digest": _digest(submissions),
                               "companyfacts_digest": _digest(companyfacts),
                               "accession_matched": True,
                               "dissemination_timestamp_proven": False},
        ))
    return tuple(sorted(rows, key=lambda row: (row.accepted_at, row.source_reference)))


class SecEdgarHistoricalFundamentalProvider:
    """Two read-only SEC API requests per CIK; user agent supplied by caller."""

    def __init__(self, user_agent: str, symbol_ciks: dict[str, int], *, transport=None):
        if "@" not in user_agent or not symbol_ciks:
            raise ValueError("Declared SEC user agent and explicit CIK mapping required")
        self._headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
        self._symbol_ciks = dict(symbol_ciks)
        self._transport = transport

    def _get(self, client: httpx.Client, path: str) -> dict:
        try:
            time.sleep(0.12)  # Keep a single process below SEC's 10 requests/second limit.
            response = client.get(f"{SEC_BASE}/{path}", headers=self._headers)
            if response.status_code != 200:
                raise ValueError(f"HTTP {response.status_code}")
            payload = response.json()
            if not isinstance(payload, dict):
                raise TypeError("Invalid SEC response")
            return payload
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            reason = str(exc) if str(exc).startswith("HTTP ") else "unavailable"
            raise ValueError(f"SEC EDGAR historical data {reason}") from None

    def statements(self, symbol: str, *, through: date,
                   since: date = date(2023, 1, 1)) -> tuple[HistoricalStatement, ...]:
        if symbol not in self._symbol_ciks:
            raise ValueError("Symbol has no explicitly pinned CIK")
        if through >= datetime.now(UTC).date() or through.year >= 2026:
            raise ValueError("Reserved out-of-sample period may not be requested")
        cik = self._symbol_ciks[symbol]
        with httpx.Client(timeout=30, transport=self._transport) as client:
            submissions = self._get(client, f"submissions/CIK{cik:010d}.json")
            for shard in submissions.get("filings", {}).get("files", ()):
                if (date.fromisoformat(shard["filingFrom"]) <= through
                        and date.fromisoformat(shard["filingTo"]) >= since):
                    _extend_recent(submissions,
                                   self._get(client, f"submissions/{shard['name']}"))
            companyfacts = self._get(client, f"api/xbrl/companyfacts/CIK{cik:010d}.json")
        rows = reconstruct_statements(symbol, cik, submissions, companyfacts,
                                      through, datetime.now(UTC))
        return tuple(row for row in rows if row.period_end >= since)
