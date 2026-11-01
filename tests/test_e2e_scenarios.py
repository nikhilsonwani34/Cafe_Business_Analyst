"""End-to-end café scenarios through the full-feasibility API pipeline."""

from datetime import datetime, timezone
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient
from httpx import Response

from app.main import app, get_geo_engine
from src.geo_engine import BoundingBox, BufferSummary, GeoDataset


class FullPipelineScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.geo_engine = Mock()
        self.geo_engine.fetch.return_value = GeoDataset(
            bounding_box=BoundingBox(12.9, 77.5, 13.1, 77.7),
            pois=(),
            retrieved_at=datetime(2026, 10, 15, tzinfo=timezone.utc),
            cache_status="hit",
        )
        self.geo_engine.analyze_buffers.return_value = (
            BufferSummary(
                radius_meters=500,
                competitor_count=7,
                demand_anchor_count=4,
            ),
            BufferSummary(
                radius_meters=1_000,
                competitor_count=19,
                demand_anchor_count=11,
            ),
        )
        app.dependency_overrides[get_geo_engine] = lambda: self.geo_engine
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    @staticmethod
    def business(
        *,
        monthly_rent: float,
        other_monthly_fixed_costs: float,
        average_ticket_size: float,
        variable_cost_per_cover: float,
        seats: int,
        operating_hours_per_day: float,
        seat_turnovers_per_hour: float,
        operating_days_per_month: int,
        expected_covers_per_day: float,
        initial_working_capital: float,
    ) -> dict:
        return {
            "monthly_rent": monthly_rent,
            "other_monthly_fixed_costs": other_monthly_fixed_costs,
            "average_ticket_size": average_ticket_size,
            "variable_cost_per_cover": variable_cost_per_cover,
            "seats": seats,
            "operating_hours_per_day": operating_hours_per_day,
            "seat_turnovers_per_hour": seat_turnovers_per_hour,
            "operating_days_per_month": operating_days_per_month,
            "expected_covers_per_day": expected_covers_per_day,
            "initial_working_capital": initial_working_capital,
        }

    @staticmethod
    def selected_site() -> dict:
        return {
            "latitude": 13.0,
            "longitude": 77.6,
            "bounding_box": {
                "south": 12.9,
                "west": 77.5,
                "north": 13.1,
                "east": 77.7,
            },
            "radii_meters": [500, 1_000],
        }

    @staticmethod
    def candidates() -> list[dict]:
        return [
            {
                "id": "koramangala-5th-block",
                "name": "Koramangala 5th Block",
                "lat": 12.9352,
                "lon": 77.6245,
                "competitor_count": 18,
                "anchor_count": 24,
                "avg_rent_per_sqft": 130,
                "accessibility_score": 0.85,
            },
            {
                "id": "indiranagar-100ft-road",
                "name": "Indiranagar 100ft Rd",
                "lat": 12.9719,
                "lon": 77.6412,
                "competitor_count": 26,
                "anchor_count": 32,
                "avg_rent_per_sqft": 165,
                "accessibility_score": 0.90,
            },
            {
                "id": "hsr-layout-sector-1",
                "name": "HSR Layout Sector 1",
                "lat": 12.9116,
                "lon": 77.6389,
                "competitor_count": 12,
                "anchor_count": 19,
                "avg_rent_per_sqft": 95,
                "accessibility_score": 0.78,
            },
            {
                "id": "jayanagar-4th-block",
                "name": "Jayanagar 4th Block",
                "lat": 12.9299,
                "lon": 77.5834,
                "competitor_count": 8,
                "anchor_count": 15,
                "avg_rent_per_sqft": 85,
                "accessibility_score": 0.75,
            },
        ]

    @staticmethod
    def criteria() -> list[dict]:
        return [
            {"name": "competitor_count", "weight": 0.25, "is_benefit": False},
            {"name": "anchor_count", "weight": 0.30, "is_benefit": True},
            {"name": "avg_rent_per_sqft", "weight": 0.25, "is_benefit": False},
            {"name": "accessibility_score", "weight": 0.20, "is_benefit": True},
        ]

    def run_full_pipeline(
        self,
        business: dict,
        candidates: list[dict] | None = None,
    ) -> Response:
        return self.client.post(
            "/api/v1/feasibility/full",
            json={
                "business": business,
                "selected_site": self.selected_site(),
                "alternative_candidates": (
                    self.candidates() if candidates is None else candidates
                ),
                "criteria": self.criteria(),
            },
        )

    @staticmethod
    def risk_rules(payload: dict) -> set[str]:
        return {
            flag["rule_name"]
            for flag in payload["risk_assessment"]["flags"]
        }

    def test_golden_baseline_has_manageable_runway_and_distinct_rankings(self) -> None:
        response = self.run_full_pipeline(
            self.business(
                monthly_rent=20_000,
                other_monthly_fixed_costs=100_000,
                average_ticket_size=280,
                variable_cost_per_cover=95,
                seats=28,
                operating_hours_per_day=12,
                seat_turnovers_per_hour=0.75,
                operating_days_per_month=30,
                expected_covers_per_day=20,
                initial_working_capital=180_000,
            )
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        financial = payload["financial"]
        self.assertEqual(financial["projected_monthly_revenue"], 168_000)
        self.assertAlmostEqual(financial["break_even_covers_per_day"], 21.6216, places=4)
        self.assertTrue(financial["break_even_within_capacity"])
        self.assertAlmostEqual(financial["cash_runway_months"], 20.0)
        self.assertEqual(self.risk_rules(payload), set())

        ranked = payload["recommendation"]["ranked_candidates"]
        self.assertEqual([item["rank"] for item in ranked], [1, 2, 3, 4])
        self.assertEqual(
            [item["candidate"]["name"] for item in ranked],
            [
                "HSR Layout Sector 1",
                "Jayanagar 4th Block",
                "Koramangala 5th Block",
                "Indiranagar 100ft Rd",
            ],
        )
        scores = [item["score"] for item in ranked]
        self.assertEqual(len(scores), len(set(scores)))
        self.assertTrue(all(item["trade_off_explanation"]["summary"] for item in ranked))
        self.geo_engine.fetch.assert_called_once()

    def test_extreme_rent_trap_flags_rental_stress_and_capacity_deficit(self) -> None:
        response = self.run_full_pipeline(
            self.business(
                monthly_rent=1_200_000,
                other_monthly_fixed_costs=100_000,
                average_ticket_size=250,
                variable_cost_per_cover=100,
                seats=20,
                operating_hours_per_day=10,
                seat_turnovers_per_hour=0.5,
                operating_days_per_month=30,
                expected_covers_per_day=100,
                initial_working_capital=100_000,
            )
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        flags = {
            flag["rule_name"]: flag
            for flag in payload["risk_assessment"]["flags"]
        }
        self.assertEqual(flags["RENTAL_STRESS"]["severity"], "CRITICAL")
        self.assertAlmostEqual(flags["RENTAL_STRESS"]["measured_value"], 1.6)
        self.assertEqual(flags["CAPACITY_DEFICIT"]["severity"], "CRITICAL")
        self.assertAlmostEqual(
            payload["financial"]["break_even_covers_per_day"],
            288.8889,
            places=4,
        )
        self.assertEqual(payload["financial"]["maximum_covers_per_day"], 100)

    def test_zero_and_negative_unit_economics_are_not_break_even_achievable(self) -> None:
        scenarios = (
            ("zero contribution", 150, 0.0, 1.0),
            ("negative contribution", 140, -10.0, 100_000 / 118_000),
        )
        for label, ticket, expected_contribution, expected_runway in scenarios:
            with self.subTest(scenario=label):
                response = self.run_full_pipeline(
                    self.business(
                        monthly_rent=40_000,
                        other_monthly_fixed_costs=60_000,
                        average_ticket_size=ticket,
                        variable_cost_per_cover=150,
                        seats=30,
                        operating_hours_per_day=12,
                        seat_turnovers_per_hour=0.5,
                        operating_days_per_month=30,
                        expected_covers_per_day=60,
                        initial_working_capital=100_000,
                    )
                )

                self.assertEqual(response.status_code, 200, response.text)
                payload = response.json()
                financial = payload["financial"]
                self.assertEqual(financial["contribution_per_cover"], expected_contribution)
                self.assertIsNone(financial["break_even_covers_per_day"])
                self.assertFalse(financial["break_even_within_capacity"])
                self.assertAlmostEqual(
                    financial["cash_runway_months"],
                    expected_runway,
                )
                flags = {
                    flag["rule_name"]: flag
                    for flag in payload["risk_assessment"]["flags"]
                }
                self.assertEqual(flags["CAPACITY_DEFICIT"]["severity"], "CRITICAL")
                self.assertEqual(
                    flags["LOW_CONTRIBUTION_MARGIN"]["severity"],
                    "WARNING",
                )
                self.assertIn(
                    "not positive",
                    flags["CAPACITY_DEFICIT"]["plain_language_explanation"],
                )

    def test_cash_depleted_startup_triggers_short_runway_warning(self) -> None:
        response = self.run_full_pipeline(
            self.business(
                monthly_rent=40_000,
                other_monthly_fixed_costs=300_000,
                average_ticket_size=300,
                variable_cost_per_cover=100,
                seats=60,
                operating_hours_per_day=12,
                seat_turnovers_per_hour=0.5,
                operating_days_per_month=30,
                expected_covers_per_day=30,
                initial_working_capital=240_000,
            )
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertAlmostEqual(payload["financial"]["monthly_cash_burn"], 160_000)
        self.assertAlmostEqual(payload["financial"]["cash_runway_months"], 1.5)
        flags = {
            flag["rule_name"]: flag
            for flag in payload["risk_assessment"]["flags"]
        }
        self.assertEqual(set(flags), {"SHORT_RUNWAY"})
        self.assertEqual(flags["SHORT_RUNWAY"]["severity"], "WARNING")

    def test_tied_alternatives_keep_input_order_across_full_pipeline(self) -> None:
        tied_candidates = self.candidates()[:2]
        tied_candidates[1] = {
            **tied_candidates[1],
            "competitor_count": tied_candidates[0]["competitor_count"],
            "anchor_count": tied_candidates[0]["anchor_count"],
            "avg_rent_per_sqft": tied_candidates[0]["avg_rent_per_sqft"],
            "accessibility_score": tied_candidates[0]["accessibility_score"],
        }

        response = self.run_full_pipeline(
            self.business(
                monthly_rent=65_000,
                other_monthly_fixed_costs=45_000,
                average_ticket_size=280,
                variable_cost_per_cover=95,
                seats=28,
                operating_hours_per_day=12,
                seat_turnovers_per_hour=0.75,
                operating_days_per_month=30,
                expected_covers_per_day=110,
                initial_working_capital=350_000,
            ),
            candidates=tied_candidates,
        )

        self.assertEqual(response.status_code, 200, response.text)
        ranked = response.json()["recommendation"]["ranked_candidates"]
        self.assertEqual([item["rank"] for item in ranked], [1, 2])
        self.assertEqual(
            [item["candidate"]["id"] for item in ranked],
            ["koramangala-5th-block", "indiranagar-100ft-road"],
        )
        self.assertEqual([item["score"] for item in ranked], [0.5, 0.5])
        self.geo_engine.fetch.assert_called_once()

    def test_incomplete_alternative_is_rejected_before_spatial_lookup(self) -> None:
        candidates = self.candidates()
        del candidates[0]["anchor_count"]

        response = self.run_full_pipeline(
            self.business(
                monthly_rent=65_000,
                other_monthly_fixed_costs=45_000,
                average_ticket_size=280,
                variable_cost_per_cover=95,
                seats=28,
                operating_hours_per_day=12,
                seat_turnovers_per_hour=0.75,
                operating_days_per_month=30,
                expected_covers_per_day=110,
                initial_working_capital=350_000,
            ),
            candidates=candidates,
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("anchor_count", str(response.json()["detail"]))
        self.geo_engine.fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
