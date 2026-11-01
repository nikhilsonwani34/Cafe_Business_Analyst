"""Deterministic café feasibility calculations.

Seat turnover is expressed as turns per seat per operating hour. Working
capital is treated as cash available after one-time setup costs.
"""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class CafeAssumptions:
    monthly_rent: float
    other_monthly_fixed_costs: float
    average_ticket_size: float
    variable_cost_per_cover: float
    seats: int
    operating_hours_per_day: float
    seat_turnovers_per_hour: float
    operating_days_per_month: int
    expected_covers_per_day: float
    initial_working_capital: float

    def __post_init__(self) -> None:
        non_negative = {
            "monthly_rent": self.monthly_rent,
            "other_monthly_fixed_costs": self.other_monthly_fixed_costs,
            "average_ticket_size": self.average_ticket_size,
            "variable_cost_per_cover": self.variable_cost_per_cover,
            "expected_covers_per_day": self.expected_covers_per_day,
            "initial_working_capital": self.initial_working_capital,
        }
        for name, value in non_negative.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(f"{name} must be a finite, non-negative number")

        if isinstance(self.seats, bool) or not isinstance(self.seats, int) or self.seats <= 0:
            raise ValueError("seats must be a positive integer")
        if (
            isinstance(self.operating_hours_per_day, bool)
            or not isinstance(self.operating_hours_per_day, (int, float))
            or not math.isfinite(self.operating_hours_per_day)
            or self.operating_hours_per_day <= 0
        ):
            raise ValueError("operating_hours_per_day must be a finite, positive number")
        if (
            isinstance(self.seat_turnovers_per_hour, bool)
            or not isinstance(self.seat_turnovers_per_hour, (int, float))
            or not math.isfinite(self.seat_turnovers_per_hour)
            or self.seat_turnovers_per_hour <= 0
        ):
            raise ValueError("seat_turnovers_per_hour must be a finite, positive number")
        if (
            isinstance(self.operating_days_per_month, bool)
            or not isinstance(self.operating_days_per_month, int)
            or self.operating_days_per_month <= 0
        ):
            raise ValueError("operating_days_per_month must be a positive integer")


@dataclass(frozen=True)
class FeasibilityResult:
    contribution_per_cover: float
    contribution_margin_ratio: float | None
    monthly_fixed_costs: float
    break_even_covers_per_month: float | None
    break_even_covers_per_day: float | None
    maximum_covers_per_day: float
    maximum_covers_per_month: float
    break_even_within_capacity: bool
    realized_expected_covers_per_day: float
    projected_monthly_revenue: float
    projected_monthly_operating_profit: float
    monthly_cash_burn: float
    cash_runway_months: float | None


def analyze_cafe(assumptions: CafeAssumptions) -> FeasibilityResult:
    """Calculate break-even, physical capacity, projected profit, and runway.

    If contribution per cover is zero or negative, break-even volume is
    undefined and the result marks the plan as not break-even-capable.
    Expected demand above physical capacity is capped for financial
    projections, while the capacity metric remains available for comparison.
    A ``None`` runway means projected operations do not consume working capital.
    """
    contribution = assumptions.average_ticket_size - assumptions.variable_cost_per_cover
    contribution_margin = (
        contribution / assumptions.average_ticket_size
        if assumptions.average_ticket_size > 0
        else None
    )
    monthly_fixed_costs = assumptions.monthly_rent + assumptions.other_monthly_fixed_costs

    if contribution > 0:
        break_even_monthly = monthly_fixed_costs / contribution
        break_even_daily = break_even_monthly / assumptions.operating_days_per_month
    else:
        break_even_monthly = None
        break_even_daily = None

    maximum_daily = (
        assumptions.seats
        * assumptions.operating_hours_per_day
        * assumptions.seat_turnovers_per_hour
    )
    maximum_monthly = maximum_daily * assumptions.operating_days_per_month
    realized_daily = min(assumptions.expected_covers_per_day, maximum_daily)
    projected_monthly_revenue = (
        realized_daily
        * assumptions.operating_days_per_month
        * assumptions.average_ticket_size
    )
    projected_profit = (
        realized_daily * assumptions.operating_days_per_month * contribution
        - monthly_fixed_costs
    )
    cash_burn = max(0.0, -projected_profit)
    runway = (
        assumptions.initial_working_capital / cash_burn
        if cash_burn > 0
        else None
    )

    return FeasibilityResult(
        contribution_per_cover=contribution,
        contribution_margin_ratio=contribution_margin,
        monthly_fixed_costs=monthly_fixed_costs,
        break_even_covers_per_month=break_even_monthly,
        break_even_covers_per_day=break_even_daily,
        maximum_covers_per_day=maximum_daily,
        maximum_covers_per_month=maximum_monthly,
        break_even_within_capacity=(
            break_even_daily is not None and break_even_daily <= maximum_daily
        ),
        realized_expected_covers_per_day=realized_daily,
        projected_monthly_revenue=projected_monthly_revenue,
        projected_monthly_operating_profit=projected_profit,
        monthly_cash_burn=cash_burn,
        cash_runway_months=runway,
    )
