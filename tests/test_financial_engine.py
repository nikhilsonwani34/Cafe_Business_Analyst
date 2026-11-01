import unittest

from src.financial_engine import CafeAssumptions, analyze_cafe


class AnalyzeCafeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assumptions = CafeAssumptions(
            monthly_rent=90_000,
            other_monthly_fixed_costs=120_000,
            average_ticket_size=300,
            variable_cost_per_cover=105,
            seats=40,
            operating_hours_per_day=12,
            seat_turnovers_per_hour=0.5,
            operating_days_per_month=30,
            expected_covers_per_day=20,
            initial_working_capital=600_000,
        )

    def test_calculates_hand_checkable_financial_metrics(self) -> None:
        result = analyze_cafe(self.assumptions)

        self.assertEqual(result.contribution_per_cover, 195)
        self.assertAlmostEqual(result.contribution_margin_ratio, 0.65)
        self.assertEqual(result.monthly_fixed_costs, 210_000)
        self.assertAlmostEqual(result.break_even_covers_per_month, 210_000 / 195)
        self.assertAlmostEqual(result.break_even_covers_per_day, 210_000 / 195 / 30)
        self.assertEqual(result.maximum_covers_per_day, 240)
        self.assertEqual(result.maximum_covers_per_month, 7_200)
        self.assertTrue(result.break_even_within_capacity)
        self.assertEqual(result.projected_monthly_revenue, 180_000)
        self.assertEqual(result.projected_monthly_operating_profit, -93_000)
        self.assertEqual(result.monthly_cash_burn, 93_000)
        self.assertAlmostEqual(result.cash_runway_months, 600_000 / 93_000)

    def test_break_even_above_physical_capacity_is_infeasible(self) -> None:
        assumptions = CafeAssumptions(
            **{
                **self.assumptions.__dict__,
                "seats": 2,
                "seat_turnovers_per_hour": 0.25,
            }
        )

        result = analyze_cafe(assumptions)

        self.assertFalse(result.break_even_within_capacity)
        self.assertLess(result.maximum_covers_per_day, result.break_even_covers_per_day)

    def test_non_positive_contribution_has_no_break_even_volume(self) -> None:
        for variable_cost in (300, 350):
            with self.subTest(variable_cost=variable_cost):
                assumptions = CafeAssumptions(
                    **{
                        **self.assumptions.__dict__,
                        "variable_cost_per_cover": variable_cost,
                    }
                )

                result = analyze_cafe(assumptions)

                self.assertLessEqual(result.contribution_per_cover, 0)
                self.assertIsNone(result.break_even_covers_per_month)
                self.assertIsNone(result.break_even_covers_per_day)
                self.assertFalse(result.break_even_within_capacity)

    def test_expected_demand_is_capped_at_physical_capacity(self) -> None:
        assumptions = CafeAssumptions(
            **{**self.assumptions.__dict__, "expected_covers_per_day": 300}
        )

        result = analyze_cafe(assumptions)

        self.assertEqual(result.realized_expected_covers_per_day, 240)
        self.assertEqual(result.projected_monthly_revenue, 2_160_000)

    def test_profitable_projection_does_not_deplete_working_capital(self) -> None:
        assumptions = CafeAssumptions(
            **{
                **self.assumptions.__dict__,
                "expected_covers_per_day": 100,
            }
        )

        result = analyze_cafe(assumptions)

        self.assertGreater(result.projected_monthly_operating_profit, 0)
        self.assertEqual(result.monthly_cash_burn, 0)
        self.assertIsNone(result.cash_runway_months)

    def test_rejects_invalid_operating_capacity_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "seats must be a positive integer"):
            CafeAssumptions(
                **{**self.assumptions.__dict__, "seats": 0}
            )

        with self.assertRaisesRegex(ValueError, "operating_days_per_month"):
            CafeAssumptions(
                **{**self.assumptions.__dict__, "operating_days_per_month": 0}
            )

        with self.assertRaisesRegex(ValueError, "monthly_rent"):
            CafeAssumptions(
                **{**self.assumptions.__dict__, "monthly_rent": "90000"}
            )

        with self.assertRaisesRegex(ValueError, "average_ticket_size"):
            CafeAssumptions(
                **{**self.assumptions.__dict__, "average_ticket_size": float("nan")}
            )


if __name__ == "__main__":
    unittest.main()
