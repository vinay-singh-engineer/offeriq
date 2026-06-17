import pytest
from app.models.offer import (
    OfferInput, EquityInput, BenefitsInput,
    PriorityWeights, CompareRequest, NegotiateRequest,
)


# --- OfferInput ---

def test_offer_input_minimal():
    offer = OfferInput(
        company_name="Acme Corp",
        role="Software Engineer",
        location="Austin, TX",
        base_salary=130000,
    )
    assert offer.base_salary == 130000
    assert offer.equity is None


def test_offer_input_full():
    offer = OfferInput(
        company_name="BigTech",
        role="Senior SWE",
        level="L5",
        location="Seattle, WA",
        base_salary=185000,
        signing_bonus=30000,
        annual_bonus_target_pct=15.0,
        equity=EquityInput(
            equity_type="rsu",
            total_grant_value=200000,
            vesting_years=4,
            cliff_months=12,
        ),
        benefits=BenefitsInput(
            healthcare_plan="ppo",
            employer_401k_match_pct=4.0,
            pto_days=20,
            remote_policy="hybrid",
        ),
    )
    assert offer.equity.equity_type == "rsu"
    assert offer.benefits.pto_days == 20


def test_offer_input_rejects_zero_salary():
    with pytest.raises(Exception):
        OfferInput(
            company_name="X",
            role="SWE",
            location="NYC",
            base_salary=0,
        )


# --- EquityInput ---

def test_rsu_requires_grant_value():
    with pytest.raises(Exception):
        EquityInput(equity_type="rsu")


def test_options_requires_shares_and_strike():
    with pytest.raises(Exception):
        EquityInput(equity_type="options", num_shares=10000)


def test_options_valid():
    eq = EquityInput(
        equity_type="options",
        num_shares=10000,
        strike_price=12.50,
        current_stock_price=25.00,
        vesting_years=4,
        cliff_months=12,
    )
    assert eq.num_shares == 10000


def test_equity_none_valid():
    eq = EquityInput(equity_type="none")
    assert eq.equity_type == "none"


# --- PriorityWeights ---

def test_default_weights_sum_to_one():
    w = PriorityWeights()
    total = w.salary + w.equity + w.benefits + w.company_health + w.work_life_balance
    assert abs(total - 1.0) < 0.001


def test_custom_weights_valid():
    w = PriorityWeights(
        salary=0.5, equity=0.2, benefits=0.1, company_health=0.1, work_life_balance=0.1
    )
    assert w.salary == 0.5


def test_weights_must_sum_to_one():
    with pytest.raises(Exception):
        PriorityWeights(
            salary=0.5, equity=0.5, benefits=0.5, company_health=0.0, work_life_balance=0.0
        )


# --- CompareRequest ---

def test_compare_request():
    offer_a = OfferInput(company_name="A", role="SWE", location="NYC", base_salary=150000)
    offer_b = OfferInput(company_name="B", role="SWE", location="SF", base_salary=180000)
    req = CompareRequest(offer_a=offer_a, offer_b=offer_b, years_of_experience=5)
    assert req.weights.salary == 0.40


# --- NegotiateRequest ---

def test_negotiate_request_with_competing_offer():
    offer = OfferInput(company_name="A", role="SWE", location="NYC", base_salary=150000)
    competing = OfferInput(company_name="B", role="SWE", location="NYC", base_salary=175000)
    req = NegotiateRequest(offer=offer, competing_offer=competing, target_salary=170000)
    assert req.target_salary == 170000
