from dataclasses import dataclass, field
from typing import List, Optional

from app.models.offer import EquityInput


@dataclass
class EquityAnalysis:
    equity_type: str
    annualized_value: float
    total_value: float
    year_one_value: float       # What actually vests in year 1 (cliff-aware)
    cliff_risk: bool            # True if cliff > 0
    is_underwater: bool         # Options only: strike > current price
    notes: List[str] = field(default_factory=list)


class EquityService:

    def analyze(self, equity: Optional[EquityInput]) -> EquityAnalysis:
        if equity is None or equity.equity_type == "none":
            return EquityAnalysis(
                equity_type="none",
                annualized_value=0.0,
                total_value=0.0,
                year_one_value=0.0,
                cliff_risk=False,
                is_underwater=False,
            )
        if equity.equity_type == "rsu":
            return self._analyze_rsu(equity)
        return self._analyze_options(equity)

    def _cliff_fraction(self, equity: EquityInput) -> float:
        """Fraction of total grant that vests at the cliff date."""
        total_months = equity.vesting_years * 12
        return equity.cliff_months / total_months if total_months > 0 else 0.0

    def _analyze_rsu(self, equity: EquityInput) -> EquityAnalysis:
        total = equity.total_grant_value
        annualized = total / equity.vesting_years
        cliff_fraction = self._cliff_fraction(equity)
        year_one_value = total * cliff_fraction if equity.cliff_months > 0 else annualized

        notes = []
        if equity.cliff_months > 0:
            notes.append(
                f"{equity.cliff_months}-month cliff: you forfeit all RSUs if you leave "
                f"before month {equity.cliff_months} "
                f"(${year_one_value:,.0f} vests at the cliff)."
            )
        notes.append(
            f"${total:,.0f} total RSU grant vesting over {equity.vesting_years} years "
            f"({equity.vesting_schedule}) = ${annualized:,.0f}/yr annualized."
        )

        return EquityAnalysis(
            equity_type="rsu",
            annualized_value=round(annualized, 2),
            total_value=round(total, 2),
            year_one_value=round(year_one_value, 2),
            cliff_risk=equity.cliff_months > 0,
            is_underwater=False,
            notes=notes,
        )

    def _analyze_options(self, equity: EquityInput) -> EquityAnalysis:
        current = equity.current_stock_price or 0.0
        strike = equity.strike_price
        shares = equity.num_shares

        intrinsic_value = max(0.0, (current - strike) * shares)
        is_underwater = current < strike
        annualized = intrinsic_value / equity.vesting_years

        cliff_fraction = self._cliff_fraction(equity)
        year_one_value = (
            intrinsic_value * cliff_fraction if equity.cliff_months > 0 else annualized
        )

        notes = []
        if is_underwater:
            notes.append(
                f"Options are underwater: strike ${strike:,.2f} > "
                f"current ${current:,.2f}. Intrinsic value is $0."
            )
        else:
            spread = current - strike
            notes.append(
                f"{shares:,} options × ${spread:,.2f} spread = "
                f"${intrinsic_value:,.0f} intrinsic value."
            )

        if equity.cliff_months > 0:
            notes.append(
                f"{equity.cliff_months}-month cliff: all options forfeit if you leave early."
            )

        notes.append(
            "Options expire ~90 days after departure — factor in liquidity risk "
            "for private company grants."
        )

        return EquityAnalysis(
            equity_type="options",
            annualized_value=round(annualized, 2),
            total_value=round(intrinsic_value, 2),
            year_one_value=round(year_one_value, 2),
            cliff_risk=equity.cliff_months > 0,
            is_underwater=is_underwater,
            notes=notes,
        )
