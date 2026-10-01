"""Accession archive reconstruction must fail closed on ambiguous evidence."""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from experiment_lab.sec_archive_evidence import (
    SecAccessionArchive,
    audit_accession,
    compare_to_companyfacts,
    extract_accession_facts,
    modeled_available_at,
    select_version,
    sha256,
)
from experiment_lab.sec_edgar_historical import reconstruct_statements

ACCEPTED = datetime(2025, 1, 30, 1, 42, 33, tzinfo=UTC)
ACCESSION = "0001628280-25-003063"
XML = b'''<xbrl xmlns="http://www.xbrl.org/2003/instance"
  xmlns:us-gaap="http://fasb.org/us-gaap/2024">
  <context id="annual"><entity><identifier scheme="http://www.sec.gov/CIK">1318605</identifier></entity>
  <period><startDate>2024-01-01</startDate><endDate>2024-12-31</endDate></period></context>
  <context id="wrong"><entity><identifier scheme="http://www.sec.gov/CIK">999</identifier></entity>
  <period><startDate>2024-01-01</startDate><endDate>2024-12-31</endDate></period></context>
  <unit id="usd"><measure>iso4217:USD</measure></unit>
  <us-gaap:PaymentsToAcquireProductiveAssets contextRef="annual" unitRef="usd">123</us-gaap:PaymentsToAcquireProductiveAssets>
  <us-gaap:PaymentsToAcquireProductiveAssets contextRef="wrong" unitRef="usd">999</us-gaap:PaymentsToAcquireProductiveAssets>
</xbrl>'''


def _statement(accession=ACCESSION, form="10-K", accepted=ACCEPTED, value=123):
    submissions = {"cik": 1318605, "filings": {"recent": {
        "accessionNumber": [accession], "filingDate": [accepted.date().isoformat()],
        "reportDate": ["2024-12-31"], "acceptanceDateTime": [accepted.isoformat()],
        "form": [form],
    }}}
    facts = {"cik": 1318605, "facts": {"us-gaap": {"PaymentsToAcquireProductiveAssets": {
        "units": {"USD": [{"accn": accession, "form": form,
                          "filed": accepted.date().isoformat(), "start": "2024-01-01",
                          "end": "2024-12-31", "val": value}]}}}}}
    return reconstruct_statements("TSLA", 1318605, submissions, facts,
                                  date(2025, 12, 31), accepted)[0]


def test_archive_extracts_exact_entity_period_and_new_supported_tag():
    facts = extract_accession_facts(XML, cik=1318605, report_end=date(2024, 12, 31),
                                    form="10-K")
    assert facts["capital_expenditure"]["value"] == Decimal(123)
    assert facts["capital_expenditure"]["tag"] == "PaymentsToAcquireProductiveAssets"
    assert extract_accession_facts(XML, cik=1, report_end=date(2024, 12, 31), form="10-K") == {}
    assert extract_accession_facts(XML, cik=1318605, report_end=date(2023, 12, 31),
                                   form="10-K") == {}


def test_archive_rejects_unsafe_and_conflicting_facts():
    with pytest.raises(ValueError):
        extract_accession_facts(b"<!DOCTYPE xbrl>" + XML, cik=1318605,
                                report_end=date(2024, 12, 31), form="10-K")
    conflict = XML.replace(b"</xbrl>", b'<us-gaap:PaymentsToAcquireProductiveAssets '
                           b'contextRef="annual" unitRef="usd">124'
                           b'</us-gaap:PaymentsToAcquireProductiveAssets></xbrl>')
    assert "capital_expenditure" not in extract_accession_facts(
        conflict, cik=1318605, report_end=date(2024, 12, 31), form="10-K")


def test_crosscheck_reports_values_and_provenance_discrepancies():
    facts = extract_accession_facts(XML, cik=1318605, report_end=date(2024, 12, 31),
                                    form="10-K")
    assert compare_to_companyfacts(facts, _statement())["capital_expenditure"] == "MATCH"
    assert compare_to_companyfacts(facts, _statement(value=124))[
        "capital_expenditure"] == "VALUE_MISMATCH"
    altered = {"capital_expenditure": {**facts["capital_expenditure"], "start": "2023-01-01"}}
    assert compare_to_companyfacts(altered, _statement())[
        "capital_expenditure"] == "CONTEXT_OR_TAG_MISMATCH"


def test_48_hour_convention_and_amendment_precedence():
    original = _statement()
    amended = _statement("0001628280-25-999999", "10-K/A", ACCEPTED + timedelta(days=60))
    assert modeled_available_at(ACCEPTED) == ACCEPTED + timedelta(hours=48)
    assert select_version((original, amended), original.period_end, ACCEPTED) is None
    assert select_version((original, amended), original.period_end,
                          ACCEPTED + timedelta(hours=48)) == original
    assert select_version((original, amended), original.period_end,
                          amended.accepted_at + timedelta(hours=48)) == amended
    assert not amended.revision_proven


def test_archive_hashes_original_and_extracted_and_refuses_overwrite(tmp_path):
    index = {"directory": {"item": [{"name": "filing.htm"},
                                     {"name": "filing_htm.xml"}]}}
    payloads = {"index.json": json.dumps(index).encode(),
                "filing.htm": b'<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"></html>',
                "filing_htm.xml": XML}

    def handler(request):
        return httpx.Response(200, content=payloads[request.url.path.rsplit("/", 1)[-1]])

    archive = SecAccessionArchive("Research contact@example.com",
                                 transport=httpx.MockTransport(handler))
    manifest = archive.fetch(cik=1318605, accession=ACCESSION,
                             primary_document="filing.htm", accepted_at=ACCEPTED,
                             output_root=tmp_path)
    target = tmp_path / "1318605" / ACCESSION
    assert all(sha256((target / name).read_bytes()) == digest
               for name, digest in manifest["sha256"].items())
    assert manifest["post_acceptance_correction_absence_proven"] is False
    audit = audit_accession(target, _statement())
    assert audit["comparison"]["capital_expenditure"] == "MATCH"
    (target / "filing_htm.xml").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        audit_accession(target, _statement())
    with pytest.raises(ValueError, match="already exists"):
        archive.fetch(cik=1318605, accession=ACCESSION, primary_document="filing.htm",
                      accepted_at=ACCEPTED, output_root=tmp_path)
    with pytest.raises(ValueError, match="OOS"):
        archive.fetch(cik=1318605, accession="0001628280-26-003063",
                      primary_document="filing.htm", accepted_at=datetime(2026, 1, 1,
                      tzinfo=UTC), output_root=tmp_path)
