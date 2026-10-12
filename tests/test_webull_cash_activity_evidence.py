import json
from types import SimpleNamespace

import pytest

from portfolio.webull_cash_activity_evidence import collect_cash_pages


def client(pages):
    tokens = []

    def read(account_id, *, pagination_key):
        tokens.append(pagination_key)
        payload = pages[len(tokens) - 1]
        return SimpleNamespace(
            status_code=200, json=lambda: payload, content=json.dumps(payload).encode()
        )

    return SimpleNamespace(list_activities=read), tokens


def test_empty_page_does_not_establish_zero_flows():
    source, _ = client([{"data": []}])
    report = collect_cash_pages(source, "private")
    assert report["currently_returned_pages_exhausted"]
    assert report["external_flow_total"] is None
    assert "ACTIVITY_PUBLICATION_UNQUALIFIED" in report["blockers"]


def test_pages_preserve_unknown_and_repeated_records_without_inference():
    row = {"unknown_field": "retain"}
    source, tokens = client([{"data": [row], "pagination_key": "next"}, {"data": [row]}])
    report = collect_cash_pages(source, "private")
    assert tokens == [None, "next"]
    assert report["records"] == [row, row]
    assert "ACTIVITY_RECORDS_UNCLASSIFIED" in report["blockers"]


def test_page_bound_is_blocker_not_exhaustion():
    source, _ = client([{"data": [], "pagination_key": "more"}])
    report = collect_cash_pages(source, "private", max_pages=1)
    assert not report["currently_returned_pages_exhausted"]
    assert "ACTIVITY_PAGE_BOUND_REACHED" in report["blockers"]


@pytest.mark.parametrize(
    "pages",
    [
        [{"data": [], "pagination_key": "same"}] * 2,
        [{"data": [], "pagination_key": True}],
        [{"data": ["invalid"]}],
        [[]],
    ],
)
def test_invalid_or_looping_pagination_fails_closed(pages):
    source, _ = client(pages)
    with pytest.raises((ValueError, TypeError)):
        collect_cash_pages(source, "private")
