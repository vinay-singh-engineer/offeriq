import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.analysis import (
    CompanyHealth, DimensionScores, MarketBenchmark, OfferAnalysis, TotalCompBreakdown,
)
from app.models.negotiation import NegotiationResult
from app.models.offer import BenefitsInput, EquityInput, NegotiateRequest, OfferInput
from app.services.negotiator import NegotiatorService


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def svc():
    return NegotiatorService(api_key="test-key")


def make_offer(salary=150000, company="Acme Corp", role="Software Engineer"):
    return OfferInput(
        company_name=company,
        role=role,
        level="Senior",
        location="Austin, TX",
        base_salary=salary,
        signing_bonus=10000,
        annual_bonus_target_pct=10.0,
        equity=EquityInput(
            equity_type="rsu",
            total_grant_value=120000,
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


def make_analysis(offer, score=62.0):
    return OfferAnalysis(
        offer=offer,
        total_comp=TotalCompBreakdown(
            base_salary=offer.base_salary,
            annual_bonus=offer.base_salary * 0.10,
            equity_annualized=30000.0,
            total=offer.base_salary + offer.base_salary * 0.10 + 30000.0,
        ),
        col_adjusted_base=115384.0,
        market_benchmark=MarketBenchmark(
            p25=133690, p50=161840, p75=208000, your_percentile=32.0
        ),
        company_health=CompanyHealth(
            layoff_risk="low",
            founding_year=2005,
            is_public=False,
            notes="Founded 2005 (21 years old). Private company.",
        ),
        dimension_scores=DimensionScores(
            salary=32.0, equity=55.0, benefits=80.0,
            company_health=85.0, work_life_balance=70.0,
        ),
        score=score,
        summary="Acme Corp — $150,000 base. Score: 62/100.",
    )


def make_result():
    return NegotiationResult(
        recommended_counter=168000,
        floor=155000,
        stretch_goal=178000,
        email_subject="Re: Software Engineer Offer — Following Up",
        email_body=(
            "Dear Hiring Manager,\n\nThank you for the offer of $150,000. "
            "Based on market data showing the median for Senior SWE in Austin "
            "is $161,840, I'd like to discuss $168,000...\n\nBest regards"
        ),
        talking_points=[
            "Market median for Senior SWE in Austin is $161,840 (BLS data).",
            "My total comp request is $168K base — 4% above median.",
            "I have a competing offer at $165K to consider.",
        ],
        leverage_notes="Salary is at 32nd percentile — clear room to negotiate.",
    )


# ── build_prompt() — pure function ────────────────────────────────────────────

def test_prompt_contains_company_name(svc):
    offer = make_offer()
    analysis = make_analysis(offer)
    req = NegotiateRequest(offer=offer)
    prompt = svc.build_prompt(req, analysis)
    assert "Acme Corp" in prompt


def test_prompt_contains_base_salary(svc):
    offer = make_offer(salary=150000)
    analysis = make_analysis(offer)
    req = NegotiateRequest(offer=offer)
    prompt = svc.build_prompt(req, analysis)
    assert "150,000" in prompt


def test_prompt_contains_market_percentile(svc):
    offer = make_offer()
    analysis = make_analysis(offer)
    req = NegotiateRequest(offer=offer)
    prompt = svc.build_prompt(req, analysis)
    assert "32" in prompt   # 32nd percentile


def test_prompt_contains_benchmark_p50(svc):
    offer = make_offer()
    analysis = make_analysis(offer)
    req = NegotiateRequest(offer=offer)
    prompt = svc.build_prompt(req, analysis)
    assert "161,840" in prompt


def test_prompt_includes_competing_offer(svc):
    offer = make_offer()
    competing = make_offer(salary=170000, company="RivalCo")
    analysis = make_analysis(offer)
    req = NegotiateRequest(offer=offer, competing_offer=competing)
    prompt = svc.build_prompt(req, analysis)
    assert "RivalCo" in prompt
    assert "170,000" in prompt


def test_prompt_includes_target_salary(svc):
    offer = make_offer()
    analysis = make_analysis(offer)
    req = NegotiateRequest(offer=offer, target_salary=175000)
    prompt = svc.build_prompt(req, analysis)
    assert "175,000" in prompt


def test_prompt_includes_yoe(svc):
    offer = make_offer()
    analysis = make_analysis(offer)
    req = NegotiateRequest(offer=offer, years_of_experience=7)
    prompt = svc.build_prompt(req, analysis)
    assert "7" in prompt


def test_prompt_includes_col_adjusted_base(svc):
    offer = make_offer()
    analysis = make_analysis(offer)
    req = NegotiateRequest(offer=offer)
    prompt = svc.build_prompt(req, analysis)
    assert "115,384" in prompt


def test_prompt_includes_company_health(svc):
    offer = make_offer()
    analysis = make_analysis(offer)
    req = NegotiateRequest(offer=offer)
    prompt = svc.build_prompt(req, analysis)
    assert "low" in prompt


# ── _parse_tool_response() ────────────────────────────────────────────────────

def test_parse_tool_response_valid(svc):
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "generate_negotiation_script"
    tool_block.input = {
        "recommended_counter": 168000,
        "floor": 155000,
        "stretch_goal": 178000,
        "email_subject": "Re: Offer",
        "email_body": "Dear...",
        "talking_points": ["Point 1", "Point 2"],
        "leverage_notes": "Strong leverage.",
    }
    mock_response = MagicMock()
    mock_response.content = [tool_block]
    result = svc._parse_tool_response(mock_response)
    assert result.recommended_counter == 168000
    assert len(result.talking_points) == 2


def test_parse_tool_response_no_tool_raises(svc):
    text_block = MagicMock()
    text_block.type = "text"
    mock_response = MagicMock()
    mock_response.content = [text_block]
    with pytest.raises(ValueError, match="did not call"):
        svc._parse_tool_response(mock_response)


# ── get_script() — mocked _call_claude ────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_script_returns_negotiation_result(svc):
    offer = make_offer()
    analysis = make_analysis(offer)
    req = NegotiateRequest(offer=offer)
    expected = make_result()

    svc._call_claude = AsyncMock(return_value=expected)
    result = await svc.get_script(req, analysis)

    assert result.recommended_counter == 168000
    assert result.floor == 155000
    assert "168" in result.email_body or "168,000" in result.email_body
    assert len(result.talking_points) >= 1


@pytest.mark.asyncio
async def test_get_script_passes_prompt_to_claude(svc):
    offer = make_offer()
    analysis = make_analysis(offer)
    req = NegotiateRequest(offer=offer)

    captured_prompt = {}

    async def capture(prompt):
        captured_prompt["value"] = prompt
        return make_result()

    svc._call_claude = capture
    await svc.get_script(req, analysis)

    assert "Acme Corp" in captured_prompt["value"]
    assert "150,000" in captured_prompt["value"]


@pytest.mark.asyncio
async def test_get_script_no_anthropic_raises_runtime_error():
    import app.services.negotiator as mod
    import app.config as cfg_mod
    original = mod._ANTHROPIC_AVAILABLE
    original_cert = cfg_mod.settings.floodgate_cert
    mod._ANTHROPIC_AVAILABLE = False
    cfg_mod.settings.floodgate_cert = ""   # force SDK path

    svc = NegotiatorService(api_key="")
    offer = make_offer()
    analysis = make_analysis(offer)
    req = NegotiateRequest(offer=offer)

    with pytest.raises(RuntimeError, match="anthropic package"):
        await svc.get_script(req, analysis)

    mod._ANTHROPIC_AVAILABLE = original
    cfg_mod.settings.floodgate_cert = original_cert


# ── _parse_raw_response() — Floodgate dict format ─────────────────────────────

def test_parse_raw_response_valid(svc):
    raw = {
        "content": [
            {
                "type": "tool_use",
                "name": "generate_negotiation_script",
                "input": {
                    "recommended_counter": 168000,
                    "floor": 155000,
                    "stretch_goal": 178000,
                    "email_subject": "Re: Offer",
                    "email_body": "Dear...",
                    "talking_points": ["Point 1"],
                    "leverage_notes": "Strong.",
                },
            }
        ]
    }
    result = svc._parse_raw_response(raw)
    assert result.recommended_counter == 168000
    assert result.talking_points == ["Point 1"]


def test_parse_raw_response_no_tool_raises(svc):
    raw = {"content": [{"type": "text", "text": "Here is my advice..."}]}
    with pytest.raises(ValueError, match="did not call"):
        svc._parse_raw_response(raw)


# ── Floodgate transport selection ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_floodgate_selected_when_cert_and_key_set(svc):
    """When FLOODGATE_CERT + KEY are set, _call_floodgate is called, not SDK."""
    offer = make_offer()
    analysis = make_analysis(offer)
    req = NegotiateRequest(offer=offer)
    expected = make_result()

    floodgate_called = {}

    async def fake_floodgate(prompt):
        floodgate_called["yes"] = True
        return expected

    svc._call_floodgate = fake_floodgate

    import app.config as cfg_mod
    original_cert = cfg_mod.settings.floodgate_cert
    original_key = cfg_mod.settings.floodgate_key
    cfg_mod.settings.floodgate_cert = "/tmp/chain.pem"
    cfg_mod.settings.floodgate_key = "/tmp/private.pem"

    try:
        await svc._call_claude(svc.build_prompt(req, analysis))
        assert floodgate_called.get("yes") is True
    finally:
        cfg_mod.settings.floodgate_cert = original_cert
        cfg_mod.settings.floodgate_key = original_key


@pytest.mark.asyncio
async def test_sdk_selected_when_no_floodgate_config(svc):
    """Without Floodgate certs, _call_anthropic_sdk is called."""
    offer = make_offer()
    analysis = make_analysis(offer)
    req = NegotiateRequest(offer=offer)
    expected = make_result()

    sdk_called = {}

    async def fake_sdk(prompt):
        sdk_called["yes"] = True
        return expected

    svc._call_anthropic_sdk = fake_sdk

    import app.config as cfg_mod
    original_cert = cfg_mod.settings.floodgate_cert
    cfg_mod.settings.floodgate_cert = ""

    try:
        await svc._call_claude(svc.build_prompt(req, analysis))
        assert sdk_called.get("yes") is True
    finally:
        cfg_mod.settings.floodgate_cert = original_cert


@pytest.mark.asyncio
async def test_floodgate_payload_uses_anthropic_model_prefix():
    """_call_floodgate must send model as 'anthropic.claude-...' not 'claude-...'."""
    import app.config as cfg_mod
    from unittest.mock import patch, MagicMock

    captured = {}

    def mock_urlopen(req, context=None):
        captured["body"] = json.loads(req.data.decode())
        raw = {
            "content": [{
                "type": "tool_use",
                "name": "generate_negotiation_script",
                "input": {
                    "recommended_counter": 168000, "floor": 155000,
                    "stretch_goal": 178000, "email_subject": "S",
                    "email_body": "B", "talking_points": ["T"],
                    "leverage_notes": "L",
                },
            }]
        }
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read = MagicMock(return_value=json.dumps(raw).encode())
        return mock_resp

    cfg_mod.settings.floodgate_cert = "/tmp/chain.pem"
    cfg_mod.settings.floodgate_key = "/tmp/private.pem"
    cfg_mod.settings.floodgate_url = "https://floodgate.example.com/api/anthropic/v1/messages"

    svc = NegotiatorService()
    offer = make_offer()
    analysis = make_analysis(offer)
    req = NegotiateRequest(offer=offer)

    try:
        with patch("ssl.create_default_context") as mock_ssl, \
             patch("urllib.request.urlopen", mock_urlopen):
            mock_ssl.return_value = MagicMock()
            mock_ssl.return_value.load_cert_chain = MagicMock()
            await svc._call_floodgate(svc.build_prompt(req, analysis))

        assert captured["body"]["model"].startswith("anthropic.")
    finally:
        cfg_mod.settings.floodgate_cert = ""
        cfg_mod.settings.floodgate_key = ""
        cfg_mod.settings.floodgate_url = ""
