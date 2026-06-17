import pytest
from app.models.offer import BenefitsInput, PriorityWeights
from app.services.scorer import ScorerService


@pytest.fixture
def svc():
    return ScorerService()


# --- score_salary ---

def test_salary_uses_percentile_directly(svc):
    assert svc.score_salary(72.0, 150000) == 72.0


def test_salary_percentile_capped_at_100(svc):
    assert svc.score_salary(105.0, 150000) == 100.0


def test_salary_fallback_high(svc):
    assert svc.score_salary(None, 220000) == 92.0


def test_salary_fallback_low(svc):
    assert svc.score_salary(None, 60000) == 22.0


# --- score_equity ---

def test_equity_zero(svc):
    assert svc.score_equity(0, 150000, False, False) == 0.0


def test_equity_50_pct_ratio(svc):
    assert svc.score_equity(75000, 150000, False, False) == 100.0


def test_equity_25_pct_ratio(svc):
    score = svc.score_equity(37500, 150000, False, False)
    assert score == 75.0


def test_equity_underwater_penalty(svc):
    score_normal = svc.score_equity(37500, 150000, False, False)
    score_underwater = svc.score_equity(37500, 150000, False, True)
    assert score_underwater == max(0.0, score_normal - 30.0)


def test_equity_cliff_penalty(svc):
    score_no_cliff = svc.score_equity(37500, 150000, False, False)
    score_cliff = svc.score_equity(37500, 150000, True, False)
    assert score_cliff == max(0.0, score_no_cliff - 10.0)


def test_equity_both_penalties_floored_at_zero(svc):
    # Very small equity + both penalties should not go negative
    score = svc.score_equity(100, 150000, True, True)
    assert score >= 0.0


# --- score_benefits ---

def test_benefits_none_returns_neutral(svc):
    assert svc.score_benefits(None, None) == 50.0


def test_benefits_full_package(svc):
    b = BenefitsInput(
        healthcare_plan="ppo",
        employer_401k_match_pct=6.0,
        pto_days=25,
        remote_policy="remote",
    )
    score = svc.score_benefits(b, 50000)
    assert score == 100.0  # 40 + 40 + 20 = 100


def test_benefits_no_401k_no_healthcare(svc):
    b = BenefitsInput(remote_policy="remote")
    score = svc.score_benefits(b, None)
    assert score == 20.0  # only unknown healthcare credit


def test_benefits_signing_bonus_boost(svc):
    b = BenefitsInput(healthcare_plan="ppo", employer_401k_match_pct=4.0)
    score_no_bonus = svc.score_benefits(b, None)
    score_with_bonus = svc.score_benefits(b, 35000)
    assert score_with_bonus == score_no_bonus + 20.0


# --- score_company_health ---

def test_company_low_risk(svc):
    assert svc.score_company_health("low") == 85.0


def test_company_high_risk(svc):
    assert svc.score_company_health("high") == 20.0


def test_company_unknown_risk(svc):
    assert svc.score_company_health("unknown") == 45.0


# --- score_wlb ---

def test_wlb_none_returns_neutral(svc):
    assert svc.score_wlb(None) == 50.0


def test_wlb_remote_with_pto(svc):
    b = BenefitsInput(remote_policy="remote", pto_days=25)
    assert svc.score_wlb(b) == 100.0  # 70 + 30


def test_wlb_onsite_no_pto(svc):
    b = BenefitsInput(remote_policy="onsite", pto_days=5)
    assert svc.score_wlb(b) == 20.0


# --- compute (weighted total) ---

def test_compute_returns_dimension_scores_and_total(svc):
    weights = PriorityWeights()
    dim, total = svc.compute(80, 60, 70, 85, 90, weights)
    assert dim.salary == 80
    assert dim.equity == 60
    assert 0 < total <= 100


def test_compute_all_100_gives_100(svc):
    weights = PriorityWeights()
    _, total = svc.compute(100, 100, 100, 100, 100, weights)
    assert total == 100.0


def test_compute_all_zero_gives_zero(svc):
    weights = PriorityWeights()
    _, total = svc.compute(0, 0, 0, 0, 0, weights)
    assert total == 0.0
