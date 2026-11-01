"""Explainable benchmark diagnostics for café feasibility results."""

from src.schemas import (
    BusinessInput,
    FinancialResult,
    RiskAssessment,
    RiskFlag,
    RiskRule,
    RiskSeverity,
)

RENT_WARNING_RATIO = 0.15
RENT_CRITICAL_RATIO = 0.18
MIN_CASH_RUNWAY_MONTHS = 3.0
MIN_CONTRIBUTION_MARGIN_RATIO = 0.50


def assess_risks(
    business_input: BusinessInput,
    financial_result: FinancialResult,
) -> RiskAssessment:
    """Evaluate rental stress, capacity, runway, and contribution margin.

    Rental burden is calculated from monthly rent divided by projected monthly
    revenue. Ratios from 15% through 18% are warnings; ratios above 18% are
    critical. No rental flag is emitted below 15%.
    """
    flags: list[RiskFlag] = []
    revenue = financial_result.projected_monthly_revenue

    if revenue == 0:
        if business_input.monthly_rent > 0:
            flags.append(
                RiskFlag(
                    rule_name=RiskRule.RENTAL_STRESS,
                    severity=RiskSeverity.CRITICAL,
                    measured_value=None,
                    threshold=RENT_CRITICAL_RATIO,
                    plain_language_explanation=(
                        "Projected monthly revenue is zero while rent is positive; "
                        "the rent-to-revenue ratio cannot be finite."
                    ),
                )
            )
    else:
        rent_ratio = business_input.monthly_rent / revenue
        if rent_ratio > RENT_CRITICAL_RATIO:
            flags.append(
                RiskFlag(
                    rule_name=RiskRule.RENTAL_STRESS,
                    severity=RiskSeverity.CRITICAL,
                    measured_value=rent_ratio,
                    threshold=RENT_CRITICAL_RATIO,
                    plain_language_explanation=(
                        f"Rent is {rent_ratio:.1%} of projected monthly revenue, "
                        "above the 18% critical benchmark."
                    ),
                )
            )
        elif rent_ratio >= RENT_WARNING_RATIO:
            flags.append(
                RiskFlag(
                    rule_name=RiskRule.RENTAL_STRESS,
                    severity=RiskSeverity.WARNING,
                    measured_value=rent_ratio,
                    threshold=RENT_WARNING_RATIO,
                    plain_language_explanation=(
                        f"Rent is {rent_ratio:.1%} of projected monthly revenue; "
                        "15% is the warning floor and ratios above 18% are critical."
                    ),
                )
            )

    break_even = financial_result.break_even_covers_per_day
    capacity = financial_result.maximum_covers_per_day
    if break_even is None or break_even > capacity:
        if break_even is None:
            explanation = (
                "Break-even is not achievable because contribution per cover is "
                "not positive."
            )
        else:
            explanation = (
                f"Daily break-even is {break_even:.2f} covers, exceeding the "
                f"physical capacity of {capacity:.2f} covers."
            )
        flags.append(
            RiskFlag(
                rule_name=RiskRule.CAPACITY_DEFICIT,
                severity=RiskSeverity.CRITICAL,
                measured_value=break_even,
                threshold=capacity,
                plain_language_explanation=explanation,
            )
        )

    runway = financial_result.cash_runway_months
    if runway is not None and runway < MIN_CASH_RUNWAY_MONTHS:
        flags.append(
            RiskFlag(
                rule_name=RiskRule.SHORT_RUNWAY,
                severity=RiskSeverity.WARNING,
                measured_value=runway,
                threshold=MIN_CASH_RUNWAY_MONTHS,
                plain_language_explanation=(
                    f"Estimated cash runway is {runway:.2f} months, below the "
                    "3-month planning benchmark."
                ),
            )
        )

    margin = financial_result.contribution_margin_ratio
    if margin is not None and margin < MIN_CONTRIBUTION_MARGIN_RATIO:
        flags.append(
            RiskFlag(
                rule_name=RiskRule.LOW_CONTRIBUTION_MARGIN,
                severity=RiskSeverity.WARNING,
                measured_value=margin,
                threshold=MIN_CONTRIBUTION_MARGIN_RATIO,
                plain_language_explanation=(
                    f"Contribution margin is {margin:.1%}, below the 50% "
                    "planning benchmark."
                ),
            )
        )

    return RiskAssessment(flags=flags)
