# OfferIQ — Job Offer Intelligence Platform

![CI](https://github.com/vinay-singh-engineer/offeriq/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

**OfferIQ** evaluates job offers the way no existing tool does — holistically.
It combines real salary benchmarks, equity normalization, cost-of-living adjustment,
and company health signals, then uses Claude AI to generate a personalized
negotiation email with your specific numbers.

> No existing tool does all three: **evaluate** + **compare** + **negotiate script**.
> Levels.fyi gives data. Glassdoor gives reviews. OfferIQ gives you the email to send.

---

## Features

| Feature | What it does |
|---|---|
| **Market Benchmark** | BLS Occupational Employment Statistics — p25/p50/p75 for your role + location |
| **Equity Normalization** | RSU vs. options, cliff-aware vesting math, underwater detection |
| **COL Adjustment** | Teleport API + COL index — normalizes salary to national purchasing power |
| **Company Health** | Wikipedia signals + 25-company layoff dataset — low/medium/high/unknown risk |
| **Offer Scorer** | Weighted 5-dimension score (salary, equity, benefits, company health, WLB) |
| **Side-by-side Comparator** | Analyzes two offers in parallel, picks a winner with reasoning |
| **AI Negotiation Coach** | Claude API (prompt caching + tool use) — counter-offer, email, talking points |
| **Demo Mode** | `GET /demo/analyze` and `GET /demo/compare` — no payload needed |

---

## Architecture

```
POST /api/analyze  ──►  AnalyzerService
                            ├── EquityService       (sync, pure math)
                            ├── BenchmarkService    (async → BLS API)
                            ├── COLService          (async → Teleport API)
                            └── CompanyService      (async → Wikipedia REST API)
                                    │
                                    ▼
                              ScorerService         (weighted 5-dimension score)
                                    │
                                    ▼
                              OfferAnalysis  ──►  POST /api/negotiate
                                                        │
                                                        ▼
                                                  NegotiatorService
                                                  (Claude claude-sonnet-4-6
                                                   prompt caching + tool use)
                                                        │
                                                        ▼
                                                  NegotiationResult
                                           (counter, floor, email, talking points)
```

---

## Quickstart

### Docker Compose (recommended)

```bash
git clone https://github.com/vinay-singh-engineer/offeriq.git
cd offeriq

cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY (required for /api/negotiate only)

docker compose up
```

### Local development

```bash
python3.9 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env  # add ANTHROPIC_API_KEY

uvicorn app.main:app --reload
```

---

## Using the UI

Once the server is running, open your browser:

| URL | What you get |
|---|---|
| `http://localhost:8000` | Web UI — form-based offer evaluation |
| `http://localhost:8000/docs` | Interactive API docs (Swagger) |
| `http://localhost:8000/demo/analyze` | Pre-built Stripe L5 analysis — no input needed |
| `http://localhost:8000/demo/compare` | Pre-built Stripe vs Google comparison |

### Analyze an offer

1. Go to `http://localhost:8000`
2. Fill in the **Offer Details** form — or click **Load Demo** to pre-fill a Stripe L5 Seattle offer
3. Click **Analyze Offer →**
4. Results appear below: overall score, dimension breakdown, market benchmark, company health

### Compare two offers

1. Click the **Compare Two Offers** tab
2. Fill in both offer forms (company, role, location, salary)
3. Click **Compare Offers →**
4. See a side-by-side analysis with a winner highlighted in green and a written recommendation

### Get a negotiation script

After analyzing an offer, a **Get Negotiation Script** section appears below the results:

1. Optionally enter a competing offer company + salary (used as leverage)
2. Optionally enter your target salary and years of experience
3. Click **Generate Script →**
4. Claude generates a personalized email subject + body + talking points citing your exact numbers

> Requires `ANTHROPIC_API_KEY` in `.env` (or a custom mTLS proxy via `FLOODGATE_*` vars).

### Reset the form

Click **Reset** at any time to clear all fields and dismiss results.

---

## API Reference

### Analyze a single offer

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "offer": {
      "company_name": "Stripe",
      "role": "Senior Software Engineer",
      "level": "L5",
      "location": "Seattle, WA",
      "base_salary": 165000,
      "signing_bonus": 25000,
      "annual_bonus_target_pct": 12,
      "equity": {
        "equity_type": "rsu",
        "total_grant_value": 200000,
        "vesting_years": 4,
        "cliff_months": 12
      },
      "benefits": {
        "healthcare_plan": "ppo",
        "employer_401k_match_pct": 4,
        "pto_days": 20,
        "remote_policy": "hybrid"
      }
    },
    "years_of_experience": 6
  }'
```

**Response highlights:**

```json
{
  "total_comp": { "base_salary": 165000, "equity_annualized": 50000, "total": 234800 },
  "col_adjusted_base": 100000,
  "market_benchmark": { "p50": 161840, "your_percentile": 54.0 },
  "dimension_scores": { "salary": 54, "equity": 72, "benefits": 80, "company_health": 45, "work_life_balance": 70 },
  "score": 64.0,
  "summary": "Stripe — $165,000 base + $50,000 equity = $234,800 total comp/yr. ..."
}
```

### Compare two offers

```bash
curl -X POST http://localhost:8000/api/compare \
  -H "Content-Type: application/json" \
  -d '{
    "offer_a": { "company_name": "Stripe", "role": "Senior SWE", "location": "Seattle, WA", "base_salary": 165000 },
    "offer_b": { "company_name": "Google", "role": "Senior SWE", "location": "Seattle, WA", "base_salary": 185000 }
  }'
```

### Get negotiation script (requires `ANTHROPIC_API_KEY`)

```bash
curl -X POST http://localhost:8000/api/negotiate \
  -H "Content-Type: application/json" \
  -d '{
    "offer": { "company_name": "Stripe", "role": "Senior SWE", "location": "Seattle, WA", "base_salary": 165000 },
    "competing_offer": { "company_name": "Google", "role": "Senior SWE", "location": "Seattle, WA", "base_salary": 185000 },
    "target_salary": 180000,
    "years_of_experience": 6
  }'
```

---

## Demo endpoints (no payload needed)

```bash
# Analyze a pre-built Stripe L5 offer
curl http://localhost:8000/demo/analyze | python3 -m json.tool

# Compare Stripe vs Google L5
curl http://localhost:8000/demo/compare | python3 -m json.tool
```

---

## Running tests

```bash
pytest tests/ -v
# 135 tests across 8 test modules
```

```bash
flake8 app tests --max-line-length=100
```

---

## Tech stack

| Layer | Tech |
|---|---|
| API | FastAPI 0.111 + Uvicorn |
| AI | Anthropic Claude claude-sonnet-4-6 (prompt caching + tool use) |
| Salary data | BLS OEWS API (free, no auth) |
| COL data | Teleport API + hardcoded ERI/Numbeo indices |
| Company data | Wikipedia REST API + layoff dataset (2022–2025) |
| Frontend | Jinja2 + Tailwind CSS (CDN) + vanilla JS |
| Infra | Docker Compose |
| CI | GitHub Actions (flake8 + pytest) |

---

## Project structure

```
offeriq/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── routes/          health · offer · demo · web
│   ├── models/          offer · analysis · comparison · negotiation
│   ├── services/        benchmarker · equity · col · company · scorer · analyzer · negotiator
│   └── templates/       index.html
├── tests/               135 tests, 8 modules
├── docker-compose.yml
├── Dockerfile
└── .github/workflows/ci.yml
```

---

## Environment variables

All config is read from `.env` at startup (via pydantic-settings). Copy `.env.example` to get started — no value is hardcoded in source.

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | For `/api/negotiate` | Claude API key from [console.anthropic.com](https://console.anthropic.com) |
| `APP_ENV` | No | `development` / `production` (default: `development`) |
| `APP_PORT` | No | Port to bind (default: `8000`) |
| `FLOODGATE_CERT` | No | Path to mTLS client cert — enables custom proxy transport when set |
| `FLOODGATE_KEY` | No | Path to mTLS private key — must be set alongside `FLOODGATE_CERT` |
| `FLOODGATE_URL` | No | Custom Claude API proxy endpoint URL |

**Transport selection:** if `FLOODGATE_CERT`, `FLOODGATE_KEY`, and `FLOODGATE_URL` are all set, the negotiate endpoint uses the mTLS transport instead of the Anthropic SDK. No values are hardcoded — all must be provided via `.env` or shell environment.

---

## What makes this different

Existing tools:

- **Levels.fyi** — salary data only, no comparison, no negotiation
- **Glassdoor** — passive data, no action layer
- **Rora** — human coaches at ~$1,500/negotiation, not self-serve

OfferIQ differentiators:
1. **Equity normalization** — cliff-aware vesting math, underwater option detection
2. **COL purchasing power** — Austin $150K = SF $311K, shown explicitly
3. **Company health signals** — age, public/private, layoff history in one risk score
4. **Negotiation scripts that cite your data** — not generic advice, your percentile, your numbers

---

## License

MIT
