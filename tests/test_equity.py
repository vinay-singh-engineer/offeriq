import pytest
from app.models.offer import EquityInput
from app.services.equity import EquityService


@pytest.fixture
def svc():
    return EquityService()


# --- None / no equity ---

def test_none_equity_returns_zeros(svc):
    result = svc.analyze(None)
    assert result.annualized_value == 0.0
    assert result.total_value == 0.0
    assert result.year_one_value == 0.0
    assert not result.cliff_risk
    assert not result.is_underwater


def test_equity_type_none_returns_zeros(svc):
    eq = EquityInput(equity_type="none")
    result = svc.analyze(eq)
    assert result.annualized_value == 0.0


# --- RSU ---

def test_rsu_annualized_value(svc):
    eq = EquityInput(equity_type="rsu", total_grant_value=200000, vesting_years=4)
    result = svc.analyze(eq)
    assert result.annualized_value == 50000.0
    assert result.total_value == 200000.0


def test_rsu_three_year_vesting(svc):
    eq = EquityInput(equity_type="rsu", total_grant_value=150000, vesting_years=3)
    result = svc.analyze(eq)
    assert result.annualized_value == 50000.0


def test_rsu_cliff_risk_flag(svc):
    eq = EquityInput(
        equity_type="rsu", total_grant_value=200000, vesting_years=4, cliff_months=12
    )
    result = svc.analyze(eq)
    assert result.cliff_risk is True


def test_rsu_no_cliff(svc):
    eq = EquityInput(
        equity_type="rsu", total_grant_value=200000, vesting_years=4, cliff_months=0
    )
    result = svc.analyze(eq)
    assert result.cliff_risk is False


def test_rsu_year_one_value_with_cliff(svc):
    # 12-month cliff on 4-year plan → 25% vests at cliff
    eq = EquityInput(
        equity_type="rsu", total_grant_value=200000, vesting_years=4, cliff_months=12
    )
    result = svc.analyze(eq)
    assert result.year_one_value == 50000.0  # 200k * (12/48)


def test_rsu_year_one_value_no_cliff(svc):
    # No cliff → year one value equals annualized
    eq = EquityInput(
        equity_type="rsu", total_grant_value=200000, vesting_years=4, cliff_months=0
    )
    result = svc.analyze(eq)
    assert result.year_one_value == 50000.0


def test_rsu_notes_mention_cliff(svc):
    eq = EquityInput(
        equity_type="rsu", total_grant_value=200000, vesting_years=4, cliff_months=12
    )
    result = svc.analyze(eq)
    assert any("cliff" in n.lower() for n in result.notes)


# --- Options: in-the-money ---

def test_options_intrinsic_value(svc):
    eq = EquityInput(
        equity_type="options",
        num_shares=10000,
        strike_price=10.0,
        current_stock_price=25.0,
        vesting_years=4,
    )
    result = svc.analyze(eq)
    assert result.total_value == 150000.0       # (25-10) * 10000
    assert result.annualized_value == 37500.0   # 150k / 4
    assert not result.is_underwater


def test_options_year_one_with_cliff(svc):
    # 12-month cliff on 4-year plan → 25% at cliff
    eq = EquityInput(
        equity_type="options",
        num_shares=10000,
        strike_price=10.0,
        current_stock_price=25.0,
        vesting_years=4,
        cliff_months=12,
    )
    result = svc.analyze(eq)
    assert result.year_one_value == 37500.0  # 150k * 0.25


# --- Options: underwater ---

def test_options_underwater(svc):
    eq = EquityInput(
        equity_type="options",
        num_shares=10000,
        strike_price=30.0,
        current_stock_price=15.0,
        vesting_years=4,
    )
    result = svc.analyze(eq)
    assert result.total_value == 0.0
    assert result.annualized_value == 0.0
    assert result.is_underwater is True


def test_options_at_the_money(svc):
    eq = EquityInput(
        equity_type="options",
        num_shares=5000,
        strike_price=20.0,
        current_stock_price=20.0,
        vesting_years=4,
    )
    result = svc.analyze(eq)
    assert result.total_value == 0.0
    assert not result.is_underwater


def test_options_no_current_price_treated_as_zero(svc):
    # current_stock_price not provided → default 0 → underwater
    eq = EquityInput(
        equity_type="options",
        num_shares=10000,
        strike_price=10.0,
        vesting_years=4,
    )
    result = svc.analyze(eq)
    assert result.is_underwater is True
    assert result.total_value == 0.0


def test_options_notes_mention_expiry(svc):
    eq = EquityInput(
        equity_type="options",
        num_shares=10000,
        strike_price=10.0,
        current_stock_price=25.0,
        vesting_years=4,
    )
    result = svc.analyze(eq)
    assert any("90 days" in n for n in result.notes)


def test_underwater_notes_flag_it(svc):
    eq = EquityInput(
        equity_type="options",
        num_shares=10000,
        strike_price=30.0,
        current_stock_price=10.0,
        vesting_years=4,
    )
    result = svc.analyze(eq)
    assert any("underwater" in n.lower() for n in result.notes)
