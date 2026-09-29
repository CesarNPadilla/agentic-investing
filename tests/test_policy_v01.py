from decimal import Decimal

import pytest

from portfolio.state import StatePosition
from tests.test_investment_policy import inputs as shared_inputs
from tests.test_investment_policy import rejected, replace, run


@pytest.fixture
def inputs():
    return shared_inputs.__wrapped__()


@pytest.mark.parametrize("field", ["thesis", "entry_thesis", "exit_invalidation_thesis"])
@pytest.mark.parametrize("value", [None, "", "   "])
def test_required_theses(inputs, field, value):
    p, o, s, t, k = inputs
    assert field in rejected(run((p, o, s, replace(t, **{field: value}), k)))


@pytest.mark.parametrize(
    "weight,warning",
    [
        ("0.20", None),
        ("0.2001", "concentration:VOO"),
        ("0.30", "concentration:VOO"),
        ("0.3001", "severe_concentration:VOO"),
    ],
)
def test_existing_holdings_and_warning_boundaries(inputs, weight, warning):
    p, o, s, t, k = inputs
    value = Decimal(weight) * 160
    position = StatePosition(
        account_id="fixture",
        symbol="VOO",
        quantity="1",
        price=value,
        cost_basis=value,
        price_as_of=o.as_of,
        asset_type="equity",
        leverage_factor="1",
    )
    account = replace(s.accounts[0], cash=160 - value, settled_cash=160 - value)
    o = replace(o, accounts=(account,), positions=(position,))
    s = replace(s, accounts=(account,), positions=(position,))
    result = run((p, o, s, t, k))
    assert result.allowed
    assert result.warnings == ((warning,) if warning else ())
    assert "proposed_order" in rejected(run((p, o, s, replace(t, symbol="VOO"), k)))
    assert not p.auto_liquidate_existing_holdings


def test_experimental_loss_is_separate_and_required(inputs):
    p, o, s, t, k = inputs
    for loss in (None, "-20", "-21"):
        assert "experimental_loss_control" in rejected(
            run((p, o, replace(s, experimental_pnl=loss), t, k))
        )
    assert "experimental_loss_control" in rejected(
        run((replace(p, max_experimental_loss=None), o, s, t, k))
    )
    assert p.audit_trail_required and p.thesis_required
    assert p.research_review_cadence == "Daily" and p.review_cadence == "Weekly"
