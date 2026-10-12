from datetime import UTC, date, datetime

import httpx
import pytest

from integrations.brokers.alpaca_paper_boundary import AlpacaPaperBoundaryReader
from market_data.base import ProviderUnavailable
from tests.test_paper_control_pipeline import reader

STAMP = int(datetime(2026, 10, 5, 4, tzinfo=UTC).timestamp())


def boundary(payload, status=200):
    def handler(request):
        assert request.method == "GET" and request.url.host == "paper-api.alpaca.markets"
        assert request.url.params["intraday_reporting"] == "continuous"
        assert request.url.params["cashflow_types"] == "ALL"
        return httpx.Response(status, json=payload)

    return AlpacaPaperBoundaryReader(
        "key",
        "secret",
        account_reader=reader(),
        transport=httpx.MockTransport(handler),
        clock=lambda: datetime(2026, 10, 5, 15, tzinfo=UTC),
    )


def test_exact_midnight_evidence_preserves_source_and_binding():
    evidence = boundary({"timestamp": [STAMP, STAMP + 60], "equity": [1000, 1000]}).read(
        date(2026, 10, 5)
    )
    assert evidence.equity == 1000
    assert evidence.as_of.hour == 0 and evidence.source_kind == "ALPACA_PAPER_CONTINUOUS_HISTORY"
    assert len(evidence.source_digest) == 64


@pytest.mark.parametrize(
    "payload",
    [
        {"timestamp": [STAMP + 60], "equity": [1000]},
        {"timestamp": [STAMP, STAMP], "equity": [1000, 1000]},
        {"timestamp": [STAMP], "equity": []},
        {"timestamp": [STAMP], "equity": [None]},
        {"timestamp": [STAMP], "equity": [0]},
        {"timestamp": [STAMP], "equity": ["NaN"]},
    ],
)
def test_missing_or_invalid_boundary_never_substitutes_nearest_point(payload):
    with pytest.raises(ProviderUnavailable):
        boundary(payload).read(date(2026, 10, 5))


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
def test_provider_failures_block(status):
    with pytest.raises(ProviderUnavailable):
        boundary({}, status).read(date(2026, 10, 5))
