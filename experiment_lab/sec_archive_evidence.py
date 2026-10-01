"""Immutable accession-specific SEC archive evidence and conservative XBRL reads."""

import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx

from experiment_lab.historical_records import HistoricalStatement
from experiment_lab.sec_edgar_historical import INSTANT, TAGS

XBRL_NS = "http://www.xbrl.org/2003/instance"
ISO_CURRENCY_NS = "http://www.xbrl.org/2003/iso4217"
MAX_ARTIFACT_BYTES = 25_000_000
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
SAFE_ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def modeled_available_at(accepted_at: datetime) -> datetime:
    """48h buffer is a research convention, not a proven dissemination time."""
    if accepted_at.tzinfo is None:
        raise ValueError("Filing acceptance needs an explicit timezone")
    return accepted_at.astimezone(UTC) + timedelta(hours=48)


def _xml_root(data: bytes):
    if len(data) > MAX_ARTIFACT_BYTES or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Unsafe or oversized accession XML")
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        raise ValueError("Invalid accession XBRL") from None
    if root.tag != f"{{{XBRL_NS}}}xbrl":
        raise ValueError("Accession artifact is not an XBRL instance")
    return root


def extract_accession_facts(xml_bytes: bytes, *, cik: int, report_end: date,
                            form: str) -> dict[str, dict]:
    """Extract only entity-wide USD facts for the exact annual/quarter period."""
    root = _xml_root(xml_bytes)
    contexts = {}
    for element in root.findall(f"{{{XBRL_NS}}}context"):
        entity = element.find(f"{{{XBRL_NS}}}entity")
        period = element.find(f"{{{XBRL_NS}}}period")
        if entity is None or period is None or len(entity) != 1:
            continue
        identifier = entity.find(f"{{{XBRL_NS}}}identifier")
        if identifier is None or not identifier.text or not identifier.text.isdecimal() or int(identifier.text) != cik:
            continue
        if element.find(f"{{{XBRL_NS}}}scenario") is not None:
            continue
        start = period.findtext(f"{{{XBRL_NS}}}startDate")
        end = period.findtext(f"{{{XBRL_NS}}}endDate")
        instant = period.findtext(f"{{{XBRL_NS}}}instant")
        contexts[element.attrib["id"]] = {"start": start, "end": end or instant,
                                           "instant": bool(instant)}
    usd_units = set()
    for unit in root.findall(f"{{{XBRL_NS}}}unit"):
        measures = unit.findall(f"{{{XBRL_NS}}}measure")
        if len(measures) == 1 and (measures[0].text or "").strip() == "iso4217:USD":
            usd_units.add(unit.attrib["id"])
    facts_by_tag = {}
    for element in root:
        if not element.tag.startswith("{http://fasb.org/us-gaap/"):
            continue
        context = contexts.get(element.attrib.get("contextRef"))
        if context is None or context["end"] != report_end.isoformat():
            continue
        if element.attrib.get("unitRef") not in usd_units or element.attrib.get("nil") == "true":
            continue
        tag = element.tag.rsplit("}", 1)[-1]
        try:
            value = Decimal((element.text or "").strip())
        except InvalidOperation:
            continue
        facts_by_tag.setdefault(tag, []).append({
            "value": value, "context": element.attrib["contextRef"],
            "start": context["start"], "end": context["end"],
            "instant": context["instant"], "unit": "USD",
        })
    selected = {}
    for metric, tags in TAGS.items():
        for tag in tags:
            candidates = []
            for fact in facts_by_tag.get(tag, ()):
                if metric in INSTANT:
                    if not fact["instant"]:
                        continue
                else:
                    if fact["instant"] or not fact["start"]:
                        continue
                    duration = (report_end - date.fromisoformat(fact["start"])).days
                    if form.startswith("10-K") and not 330 <= duration <= 380:
                        continue
                    if form.startswith("10-Q") and not 60 <= duration <= 110:
                        continue
                candidates.append(fact)
            if candidates:
                if len({(f["start"], f["value"]) for f in candidates}) == 1:
                    selected[metric] = {"tag": tag, **candidates[0]}
                # Ambiguity blocks fallback to a second tag.
                break
    return selected


def compare_to_companyfacts(archived: dict[str, dict], statement: HistoricalStatement) -> dict:
    comparison = {}
    provenance = statement.provider_metadata.get("fact_provenance", {})
    for metric in sorted(set(archived) | set(statement.normalized_values)):
        if metric not in archived:
            status = "MISSING_ARCHIVE_FACT"
        elif metric not in statement.normalized_values:
            status = "MISSING_COMPANYFACTS_FACT"
        elif metric not in provenance or (archived[metric]["tag"] != provenance[metric]["tag"]
              or archived[metric]["start"] != provenance[metric]["start"]):
            status = "CONTEXT_OR_TAG_MISMATCH"
        elif archived[metric]["value"] != statement.normalized_values[metric]:
            status = "VALUE_MISMATCH"
        else:
            status = "MATCH"
        comparison[metric] = status
    return comparison


def audit_accession(directory: Path, statement: HistoricalStatement) -> dict:
    """Recheck preserved bytes before comparing one original filing version."""
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if (statement.source_reference != manifest.get("accession")
            or statement.provider_metadata.get("cik") != manifest.get("cik")
            or statement.accepted_at is None
            or statement.accepted_at.astimezone(UTC).isoformat()
            != datetime.fromisoformat(manifest["accepted_at"]).astimezone(UTC).isoformat()):
        raise ValueError("Accession manifest does not match filing record")
    if manifest.get("availability_convention") != "ACCEPTANCE_PLUS_48_HOURS_NOT_PROOF":
        raise ValueError("Unknown archive availability convention")
    if (datetime.fromisoformat(manifest["modeled_available_at"])
            != modeled_available_at(statement.accepted_at)):
        raise ValueError("Modeled availability mismatch")
    hashes = manifest.get("sha256", {})
    expected = {"index.json", manifest["primary_document"],
                manifest["extracted_instance"]}
    if set(hashes) != expected or any(not SAFE_NAME.fullmatch(name) for name in hashes):
        raise ValueError("Incomplete or unsafe archive manifest")
    for name, digest in hashes.items():
        if sha256((directory / name).read_bytes()) != digest:
            raise ValueError("Accession artifact hash mismatch")
    instance = (directory / manifest["extracted_instance"]).read_bytes()
    facts = extract_accession_facts(instance, cik=manifest["cik"],
                                    report_end=statement.period_end,
                                    form=statement.statement_type)
    comparison = compare_to_companyfacts(facts, statement)
    return {"accession": statement.source_reference, "form": statement.statement_type,
            "archive_fact_count": len(facts),
            "companyfacts_fact_count": len(statement.normalized_values),
            "comparison": comparison, "artifact_sha256": hashes,
            "revision_proven": False,
            "post_acceptance_correction_absence_proven": False}


def select_version(statements: tuple[HistoricalStatement, ...], period_end: date,
                   at: datetime) -> HistoricalStatement | None:
    """Later accepted amendments take precedence after the modeled delay."""
    eligible = [row for row in statements if row.period_end == period_end
                and row.accepted_at is not None
                and modeled_available_at(row.accepted_at) <= at]
    return max(eligible, key=lambda row: (row.accepted_at, row.source_reference)) if eligible else None


class SecAccessionArchive:
    def __init__(self, user_agent: str, *, transport=None):
        if "@" not in user_agent:
            raise ValueError("Declared SEC contact User-Agent required")
        self._headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
        self._transport = transport

    def _get(self, client: httpx.Client, url: str) -> bytes:
        try:
            time.sleep(0.12)
            response = client.get(url, headers=self._headers)
            if response.status_code != 200:
                raise ValueError(f"HTTP {response.status_code}")
            if len(response.content) > MAX_ARTIFACT_BYTES:
                raise ValueError("Oversized archive artifact")
            return response.content
        except (httpx.HTTPError, ValueError) as exc:
            reason = str(exc) if str(exc).startswith("HTTP ") else "unavailable"
            raise ValueError(f"SEC accession archive {reason}") from None

    def fetch(self, *, cik: int, accession: str, primary_document: str,
              accepted_at: datetime, output_root: Path) -> dict:
        if (not SAFE_ACCESSION.fullmatch(accession)
                or not SAFE_NAME.fullmatch(primary_document)):
            raise ValueError("Invalid accession or primary document")
        if accepted_at.tzinfo is None or accepted_at.astimezone(UTC).year >= 2026:
            raise ValueError("Reserved OOS accession cannot be fetched")
        target = output_root / str(cik) / accession
        if target.exists():
            raise ValueError("Immutable accession archive already exists")
        base = (f"https://www.sec.gov/Archives/edgar/data/{cik}/"
                f"{accession.replace('-', '')}/")
        with httpx.Client(timeout=30, transport=self._transport) as client:
            index_bytes = self._get(client, base + "index.json")
            index = json.loads(index_bytes)
            names = {item["name"] for item in index["directory"]["item"]}
            if not primary_document.endswith(".htm"):
                raise ValueError("Primary document must be inline HTML")
            extracted = primary_document[:-4] + "_htm.xml"
            if primary_document not in names or extracted not in names:
                raise ValueError("Original or matching extracted XBRL artifact unavailable")
            primary_bytes = self._get(client, base + primary_document)
            instance_bytes = self._get(client, base + extracted)
        if b"xmlns:ix" not in primary_bytes[:10000] and b"<ix:" not in primary_bytes:
            raise ValueError("Primary artifact is not verifiable inline XBRL")
        _xml_root(instance_bytes)
        target.mkdir(parents=True, exist_ok=False)
        for name, data in (("index.json", index_bytes), (primary_document, primary_bytes),
                           (extracted, instance_bytes)):
            (target / name).write_bytes(data)
        manifest = {
            "cik": cik, "accession": accession, "accepted_at": accepted_at.isoformat(),
            "modeled_available_at": modeled_available_at(accepted_at).isoformat(),
            "availability_convention": "ACCEPTANCE_PLUS_48_HOURS_NOT_PROOF",
            "retrieved_at": datetime.now(UTC).isoformat(),
            "source": base, "primary_document": primary_document,
            "extracted_instance": extracted,
            "sha256": {"index.json": sha256(index_bytes),
                       primary_document: sha256(primary_bytes),
                       extracted: sha256(instance_bytes)},
            "post_acceptance_correction_absence_proven": False,
            "oos_exposed": False,
        }
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                               encoding="utf-8")
        return manifest
