import re
import httpx
from typing import Optional

from app.models.analysis import CompanyHealth


# Known layoffs 2022-2025 (public record). Key = lowercase company name keyword.
KNOWN_LAYOFFS: dict = {
    "google": {"count": 12000, "year": 2023},
    "alphabet": {"count": 12000, "year": 2023},
    "amazon": {"count": 18000, "year": 2023},
    "microsoft": {"count": 10000, "year": 2023},
    "meta": {"count": 11000, "year": 2023},
    "facebook": {"count": 11000, "year": 2022},
    "twitter": {"count": 7500, "year": 2022},
    "x corp": {"count": 7500, "year": 2022},
    "salesforce": {"count": 8000, "year": 2023},
    "lyft": {"count": 1072, "year": 2023},
    "stripe": {"count": 1120, "year": 2023},
    "coinbase": {"count": 950, "year": 2023},
    "spotify": {"count": 1500, "year": 2024},
    "intel": {"count": 15000, "year": 2024},
    "cisco": {"count": 4000, "year": 2024},
    "paypal": {"count": 2500, "year": 2024},
    "ebay": {"count": 1000, "year": 2024},
    "tesla": {"count": 14000, "year": 2024},
    "apple": {"count": 600, "year": 2024},
    "qualcomm": {"count": 1400, "year": 2024},
    "workday": {"count": 1750, "year": 2024},
    "dropbox": {"count": 500, "year": 2023},
    "zoom": {"count": 1300, "year": 2023},
    "doordash": {"count": 1250, "year": 2022},
}

# Regex patterns to extract signals from Wikipedia extracts
_YEAR_FOUNDED = re.compile(
    r"founded\s+(?:in\s+)?(\d{4})|incorporated\s+(?:in\s+)?(\d{4})", re.IGNORECASE
)
_IS_PUBLIC = re.compile(
    r"\b(?:NYSE|NASDAQ|stock\s+exchange|publicly\s+traded|initial\s+public\s+offering|IPO)\b",
    re.IGNORECASE,
)
_IS_PRIVATE = re.compile(r"\bprivate\s+company\b|\bprivately\s+held\b", re.IGNORECASE)

WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
_CURRENT_YEAR = 2026


class CompanyService:

    def _find_layoffs(self, company_name: str) -> Optional[dict]:
        name_lower = company_name.lower()
        for keyword, data in KNOWN_LAYOFFS.items():
            if keyword in name_lower:
                return data
        return None

    def _parse_founding_year(self, extract: str) -> Optional[int]:
        match = _YEAR_FOUNDED.search(extract)
        if match:
            year_str = match.group(1) or match.group(2)
            year = int(year_str)
            if 1800 < year <= _CURRENT_YEAR:
                return year
        return None

    def _parse_is_public(self, extract: str) -> bool:
        if _IS_PRIVATE.search(extract):
            return False
        return bool(_IS_PUBLIC.search(extract))

    def _compute_risk(
        self,
        founding_year: Optional[int],
        is_public: bool,
        recent_layoffs: bool,
    ) -> str:
        age = (_CURRENT_YEAR - founding_year) if founding_year else None

        if recent_layoffs:
            # Large established public companies doing restructuring = medium
            if is_public and (age is None or age > 10):
                return "medium"
            return "high"

        if age is not None:
            if age < 3:
                return "high"
            if age < 7 and not is_public:
                return "medium"

        if is_public:
            return "low"

        return "unknown"

    def _build_notes(
        self,
        company_name: str,
        founding_year: Optional[int],
        is_public: bool,
        layoff_data: Optional[dict],
    ) -> str:
        parts = []
        if founding_year:
            age = _CURRENT_YEAR - founding_year
            parts.append(f"Founded {founding_year} ({age} years old).")
        parts.append("Publicly traded." if is_public else "Private company.")
        if layoff_data:
            parts.append(
                f"Recent layoffs: ~{layoff_data['count']:,} employees "
                f"({layoff_data['year']})."
            )
        return " ".join(parts)

    async def _fetch_wikipedia(self, company_name: str) -> Optional[dict]:
        title = company_name.replace(" ", "_")
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(WIKI_SUMMARY_URL.format(title=title))
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                data = resp.json()
                if data.get("type") in ("disambiguation", "https://mediawiki.org/wiki/HyperSwitch"):
                    return None
                return data
        except Exception:
            return None

    async def get_health(self, company_name: str) -> CompanyHealth:
        layoff_data = self._find_layoffs(company_name)
        wiki = await self._fetch_wikipedia(company_name)

        founding_year: Optional[int] = None
        is_public = False

        if wiki and wiki.get("extract"):
            extract = wiki["extract"]
            founding_year = self._parse_founding_year(extract)
            is_public = self._parse_is_public(extract)

        recent_layoffs = layoff_data is not None
        risk = self._compute_risk(founding_year, is_public, recent_layoffs)
        notes = self._build_notes(company_name, founding_year, is_public, layoff_data)

        return CompanyHealth(
            layoff_risk=risk,
            recent_layoffs=recent_layoffs,
            founding_year=founding_year,
            is_public=is_public,
            notes=notes,
        )
