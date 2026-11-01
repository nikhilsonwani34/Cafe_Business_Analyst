import unittest

from pydantic import ValidationError

from src.financial_engine import CafeAssumptions, analyze_cafe
from src.risk_engine import assess_risks
from src.schemas import (
    BusinessInput,
    FinancialResult,
    RiskRule,
    RiskSeverity,
)


class RiskEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base_input = BusinessInput(
            monthly_rent=90_000,
            other_monthly_fixed_costs=120_000,
            average_ticket_size=300,
            variable_cost_per_cover=105,
            seats=40,
            operating_hours_per_day=12,
            seat_turnovers_per_hour=0.5,
            operating_days_per_month=30,
            expected_covers_per_day=100,
            initial_working_capital=600_000,
        )

    def assess(self, **overrides: object):
        input_values = self.base_input.model_dump()
        input_values.update(overrides)
        business_input = BusinessInput.model_validate(input_values)
        engine_input = CafeAssumptions(**business_input.model_dump())
        financial_result = FinancialResult.model_validate(analyze_cafe(engine_input))
        return business_input, assess_risks(business_input, financial_result)

    def test_rental_stress_is_critical_above_18_percent(self) -> None:
        business_input, assessment = self.assess(monthly_rent=171_000)

        flag = self.get_flag(assessment.flags, RiskRule.RENTAL_STRESS)

        self.assertEqual(flag.severity, RiskSeverity.CRITICAL)
        self.assertAlmostEqual(
            flag.measured_value,
            business_input.monthly_rent / 900_000,
        )
        self.assertEqual(flag.threshold, 0.18)
        self.assert_flag_contract(flag)

    def test_rental_warning_band_and_18_percent_boundary(self) -> None:
        for rent, expected_ratio in ((135_000, 0.15), (162_000, 0.18)):
            with self.subTest(rent=rent):
                _, assessment = self.assess(monthly_rent=rent)
                flag = self.get_flag(assessment.flags, RiskRule.RENTAL_STRESS)

                self.assertEqual(flag.severity, RiskSeverity.WARNING)
                self.assertAlmostEqual(flag.measured_value, expected_ratio)
                self.assertEqual(flag.threshold, 0.15)

    def test_rental_below_warning_floor_has_no_flag(self) -> None:
        _, assessment = self.assess(monthly_rent=134_999)

        self.assertIsNone(self.find_flag(assessment.flags, RiskRule.RENTAL_STRESS))

    def test_positive_rent_and_zero_projected_revenue_is_critical(self) -> None:
        _, assessment = self.assess(
            monthly_rent=1,
            expected_covers_per_day=0,
        )

        flag = self.get_flag(assessment.flags, RiskRule.RENTAL_STRESS)

        self.assertEqual(flag.severity, RiskSeverity.CRITICAL)
        self.assertIsNone(flag.measured_value)
        self.assertEqual(flag.threshold, 0.18)
        self.assert_flag_contract(flag)

    def test_capacity_deficit_when_break_even_exceeds_capacity(self) -> None:
        _, assessment = self.assess(
            seats=2,
            seat_turnovers_per_hour=0.25,
        )

        flag = self.get_flag(assessment.flags, RiskRule.CAPACITY_DEFICIT)

        self.assertEqual(flag.severity, RiskSeverity.CRITICAL)
        self.assertGreater(flag.measured_value, flag.threshold)
        self.assert_flag_contract(flag)

    def test_capacity_boundary_at_break_even_is_not_a_deficit(self) -> None:
        business_input = self.base_input.model_copy(
            update={
                "monthly_rent": 0,
                "other_monthly_fixed_costs": 2_925,
                "seats": 1,
                "operating_hours_per_day": 1,
                "seat_turnovers_per_hour": 0.5,
            }
        )
        engine_input = CafeAssumptions(**business_input.model_dump())
        financial_result = FinancialResult.model_validate(analyze_cafe(engine_input))
        assessment = assess_risks(business_input, financial_result)

        self.assertAlmostEqual(financial_result.break_even_covers_per_day, 0.5)
        self.assertEqual(financial_result.maximum_covers_per_day, 0.5)
        self.assertIsNone(self.find_flag(assessment.flags, RiskRule.CAPACITY_DEFICIT))

    def test_non_achievable_break_even_is_capacity_critical(self) -> None:
        _, assessment = self.assess(variable_cost_per_cover=300)

        flag = self.get_flag(assessment.flags, RiskRule.CAPACITY_DEFICIT)

        self.assertEqual(flag.severity, RiskSeverity.CRITICAL)
        self.assertIsNone(flag.measured_value)
        self.assert_flag_contract(flag)

    def test_short_runway_below_three_months_is_warning(self) -> None:
        _, assessment = self.assess(
            expected_covers_per_day=20,
            initial_working_capital=100_000,
        )

        flag = self.get_flag(assessment.flags, RiskRule.SHORT_RUNWAY)

        self.assertEqual(flag.severity, RiskSeverity.WARNING)
        self.assertLess(flag.measured_value, 3)
        self.assertEqual(flag.threshold, 3)
        self.assert_flag_contract(flag)

    def test_runway_at_three_months_has_no_short_runway_flag(self) -> None:
        business_input = self.base_input.model_copy(
            update={
                "expected_covers_per_day": 20,
                "initial_working_capital": 279_000,
            }
        )
        engine_input = CafeAssumptions(**business_input.model_dump())
        financial_result = FinancialResult.model_validate(analyze_cafe(engine_input))

        self.assertAlmostEqual(financial_result.cash_runway_months, 3)
        assessment = assess_risks(business_input, financial_result)
        self.assertIsNone(self.find_flag(assessment.flags, RiskRule.SHORT_RUNWAY))

    def test_low_contribution_margin_below_50_percent_is_warning(self) -> None:
        _, assessment = self.assess(variable_cost_per_cover=160)

        flag = self.get_flag(assessment.flags, RiskRule.LOW_CONTRIBUTION_MARGIN)

        self.assertEqual(flag.severity, RiskSeverity.WARNING)
        self.assertLess(flag.measured_value, 0.5)
        self.assertEqual(flag.threshold, 0.5)
        self.assert_flag_contract(flag)

    def test_contribution_margin_at_50_percent_has_no_flag(self) -> None:
        _, assessment = self.assess(variable_cost_per_cover=150)

        self.assertIsNone(
            self.find_flag(assessment.flags, RiskRule.LOW_CONTRIBUTION_MARGIN)
        )

    def test_healthy_baseline_has_no_critical_flags(self) -> None:
        _, assessment = self.assess()

        self.assertEqual(assessment.critical_count, 0)
        self.assertEqual(assessment.warning_count, 0)
        self.assertEqual(assessment.flags, [])

    def test_business_input_rejects_invalid_values(self) -> None:
        with self.assertRaises(ValidationError):
            BusinessInput.model_validate(
                {**self.base_input.model_dump(), "average_ticket_size": 0}
            )

        with self.assertRaises(ValidationError):
            BusinessInput.model_validate(
                {**self.base_input.model_dump(), "seats": 0}
            )

        with self.assertRaises(ValidationError):
            BusinessInput.model_validate(
                {**self.base_input.model_dump(), "monthly_rent": -1}
            )

    @staticmethod
    def find_flag(flags, rule_name):
        return next((flag for flag in flags if flag.rule_name is rule_name), None)

    def get_flag(self, flags, rule_name):
        flag = self.find_flag(flags, rule_name)
        self.assertIsNotNone(flag, f"Expected {rule_name.value} flag")
        return flag

    def assert_flag_contract(self, flag) -> None:
        self.assertIsNotNone(flag.rule_name)
        self.assertIsNotNone(flag.severity)
        self.assertIsNotNone(flag.plain_language_explanation)
        self.assertTrue(flag.plain_language_explanation)
        self.assertIn("measured_value", flag.model_fields_set)
        self.assertIn("threshold", flag.model_fields_set)


if __name__ == "__main__":
    unittest.main()
