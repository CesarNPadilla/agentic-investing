from strategies.paper_plumbing import candidate


def test_smallest_whole_share_intent_meets_minimum_and_never_executes():
    x = candidate(
        ask="20", current_account_equity=1000, current_sleeve_equity=1000, settled_cash=1000
    )
    assert x["quantity"] == 2 and x["action"] == "BUY_INTENT_ONLY"
    assert not x["execution_available"] and x["requires_full_risk_review"]


def test_concentration_minimum_and_existing_exposure_hold():
    args = {
        "ask": 120,
        "current_account_equity": 1000,
        "current_sleeve_equity": 1000,
        "settled_cash": 1000,
    }
    assert candidate(**args)["action"] == "HOLD"
    args["ask"] = 20
    assert candidate(**args, has_position=True)["action"] == "HOLD"
    assert candidate(**args, has_open_order=True)["action"] == "HOLD"
    args["settled_cash"] = 30
    assert candidate(**args)["action"] == "HOLD"
