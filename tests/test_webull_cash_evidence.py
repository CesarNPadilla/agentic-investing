from types import SimpleNamespace

import pytest

from integrations.brokers.webull_cash_evidence import WebullCashEvidenceReader, account_binding


def fixture():
    selection = {
        "account_id": "private",
        "account_binding_sha256": account_binding("private"),
        "environment": "sandbox",
        "endpoint": "api.sandbox.webull.com",
        "account_class": "INDIVIDUAL_CASH",
        "execution_available": False,
        "trial_started": False,
    }
    balance = {
        "total_asset_currency": "USD",
        "total_net_liquidation_value": "1000000",
        "total_cash_balance": "1000000",
        "account_currency_assets": [
            {"currency": "USD", "settled_cash": "1000000", "unsettled_cash": "0"}
        ],
    }

    def response(payload):
        return SimpleNamespace(status_code=200, json=lambda: payload)

    client = SimpleNamespace(
        account_v2=SimpleNamespace(
            get_account_list=lambda: response(
                [
                    {
                        "account_id": "private",
                        "account_class": "INDIVIDUAL_CASH",
                        "account_type": "CASH",
                    }
                ]
            ),
            get_account_balance=lambda _: response(balance),
            get_account_position=lambda _: response([]),
        ),
        order_v3=SimpleNamespace(get_order_open=lambda _: response([])),
    )
    return selection, balance, client, response


def test_bound_observation_preserves_source_blockers_and_sleeve_cap():
    selection, _, client, _ = fixture()
    report = WebullCashEvidenceReader(client, selection).observe()
    assert report["observed_equity_usd"] == "1000000"
    assert report["experimental_sleeve_ceiling_usd"] == "1000"
    assert "ACCOUNT_ASOF_UNQUALIFIED" in report["blockers"]
    assert not report["execution_available"] and "account_id" not in report


@pytest.mark.parametrize(
    "change",
    [
        {"environment": "production"},
        {"trial_started": True},
        {"account_binding_sha256": "invalid"},
        {"account_class": "INDIVIDUAL_MARGIN"},
    ],
)
def test_invalid_selection_rejected_before_source_access(change):
    selection, _, _, _ = fixture()
    with pytest.raises(ValueError):
        WebullCashEvidenceReader(None, selection | change)


def test_binding_must_match_fresh_discovery():
    selection, _, client, response = fixture()
    client.account_v2.get_account_list = lambda: response([])
    with pytest.raises(ValueError):
        WebullCashEvidenceReader(client, selection).observe()


def test_cash_breakdown_mismatch_rejected():
    selection, balance, client, _ = fixture()
    balance["account_currency_assets"][0]["settled_cash"] = "900000"
    with pytest.raises(ValueError):
        WebullCashEvidenceReader(client, selection).observe()


def test_balance_change_during_bracket_rejected():
    selection, balance, client, response = fixture()
    calls = []

    def balance_read(_):
        calls.append(True)
        return response(
            balance if len(calls) == 1 else balance | {"total_net_liquidation_value": "999999"}
        )

    client.account_v2.get_account_balance = balance_read
    with pytest.raises(ValueError):
        WebullCashEvidenceReader(client, selection).observe()


def test_existing_exposure_is_reported_and_remains_blocked():
    selection, _, client, response = fixture()
    client.account_v2.get_account_position = lambda _: response([{"symbol": "SCHB"}])
    report = WebullCashEvidenceReader(client, selection).observe()
    assert "EXISTING_EXPOSURE_HUMAN_REVIEW_REQUIRED" in report["blockers"]
    assert report["execution_available"] is False
