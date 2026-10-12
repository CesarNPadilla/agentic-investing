import httpx
import pytest

from scripts.check_alpaca_paper import PAPER_URL, preflight


def credentials(tmp_path):
    path = tmp_path / "paper.env"
    path.write_text("AIL_ALPACA_API_KEY=test-key\nAIL_ALPACA_API_SECRET=test-secret\n", encoding="utf-8")
    return path


def test_preflight_only_reads_fixed_paper_host_and_omits_private_data(tmp_path):
    requests = []
    def handler(request):
        requests.append(request)
        assert request.method == "GET"
        assert request.url.host == "paper-api.alpaca.markets"
        if request.url.path == "/v2/account":
            return httpx.Response(200, json={"status": "ACTIVE", "id": "private-id",
                "equity": "100000", "trading_blocked": False, "account_blocked": False,
                "trade_suspended_by_user": False})
        return httpx.Response(200, json=[])
    report = preflight(credentials(tmp_path), transport=httpx.MockTransport(handler))
    assert report["account_access_verified"] and report["empty_account_verified"]
    assert report["account_unblocked_verified"]
    assert len(requests) == 3
    assert "private-id" not in str(report) and "100000" not in str(report)
    assert not report["order_submission_available"] and not report["runtime_started"]


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
def test_failure_or_redirect_never_follows_or_exposes_response(tmp_path, status):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(status, text="private-secret", headers={"Location": "https://api.alpaca.markets/v2/account"})
    report = preflight(credentials(tmp_path), transport=httpx.MockTransport(handler))
    assert not report["account_access_verified"] and report["errors"]
    assert len(requests) == 1 and "private-secret" not in str(report)


def test_nonempty_account_is_never_cleared_or_reported_empty(tmp_path):
    def handler(request):
        if request.url.path == "/v2/account":
            return httpx.Response(200, json={"status": "ACTIVE"})
        return httpx.Response(200, json=[{"id": "private"}])
    report = preflight(credentials(tmp_path), transport=httpx.MockTransport(handler))
    assert not report["empty_account_verified"] and not report["account_unblocked_verified"]
    assert "private" not in str(report)


def test_missing_credentials_never_requests_network(tmp_path):
    def handler(request):
        pytest.fail("Network request with missing credentials")
    report = preflight(tmp_path / "missing.env", transport=httpx.MockTransport(handler))
    assert report["errors"] and not report["account_access_verified"]
