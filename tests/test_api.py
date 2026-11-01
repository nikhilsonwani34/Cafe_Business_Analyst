from datetime import datetime, timezone
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.main import app, get_geo_engine
from src.geo_engine import BoundingBox, BufferSummary, GeoDataError, GeoDataset


class ApiIntegrationTests(unittest.TestCase):
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
    def business_input() -> dict:
        return {
            "monthly_rent": 90_000,
            "other_monthly_fixed_costs": 120_000,
            "average_ticket_size": 300,
            "variable_cost_per_cover": 105,
            "seats": 40,
            "operating_hours_per_day": 12,
            "seat_turnovers_per_hour": 0.5,
            "operating_days_per_month": 30,
            "expected_covers_per_day": 100,
            "initial_working_capital": 600_000,
        }

    @staticmethod
    def spatial_request() -> dict:
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
                "id": "candidate-a",
                "name": "Candidate A",
                "lat": 13.0,
                "lon": 77.6,
                "competitor_count": 8,
                "anchor_count": 12,
                "avg_rent_per_sqft": 110,
                "accessibility_score": 0.8,
            },
            {
                "id": "candidate-b",
                "name": "Candidate B",
                "lat": 13.01,
                "lon": 77.61,
                "competitor_count": 4,
                "anchor_count": 7,
                "avg_rent_per_sqft": 80,
                "accessibility_score": 0.6,
            },
        ]

    @staticmethod
    def criteria() -> list[dict]:
        return [
            {
                "name": "anchor_count",
                "weight": 0.5,
                "is_benefit": True,
            },
            {
                "name": "avg_rent_per_sqft",
                "weight": 0.5,
                "is_benefit": False,
            },
        ]

    def test_health_endpoint_returns_loaded_status(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "healthy", "engines": "loaded"},
        )

    def test_financial_endpoint_returns_metrics_and_risk_diagnostics(self) -> None:
        response = self.client.post(
            "/api/v1/financial/evaluate",
            json={"business": self.business_input()},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["financial"]["monthly_fixed_costs"], 210_000)
        self.assertEqual(payload["financial"]["projected_monthly_revenue"], 900_000)
        self.assertEqual(payload["risk_assessment"]["flags"], [])

    def test_financial_endpoint_rejects_invalid_business_inputs(self) -> None:
        business = self.business_input()
        business["average_ticket_size"] = 0

        response = self.client.post(
            "/api/v1/financial/evaluate",
            json={"business": business},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("detail", response.json())

    def test_spatial_endpoint_uses_injected_engine_and_returns_provenance(self) -> None:
        response = self.client.post(
            "/api/v1/spatial/analyze",
            json=self.spatial_request(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summaries"][0]["competitor_count"], 7)
        self.assertEqual(payload["summaries"][1]["demand_anchor_count"], 11)
        self.assertEqual(payload["cache_status"], "hit")
        self.assertEqual(payload["license"], "ODbL-1.0")
        self.assertEqual(payload["attribution"], "© OpenStreetMap contributors")
        self.geo_engine.fetch.assert_called_once()
        self.geo_engine.analyze_buffers.assert_called_once()

    def test_spatial_endpoint_rejects_coordinates_outside_query_bounds(self) -> None:
        spatial = self.spatial_request()
        spatial["latitude"] = 14

        response = self.client.post("/api/v1/spatial/analyze", json=spatial)

        self.assertEqual(response.status_code, 422)
        self.geo_engine.fetch.assert_not_called()

    def test_spatial_upstream_failure_returns_502(self) -> None:
        self.geo_engine.fetch.side_effect = GeoDataError("Overpass request failed")

        response = self.client.post(
            "/api/v1/spatial/analyze",
            json=self.spatial_request(),
        )

        self.assertEqual(response.status_code, 502)
        self.assertIn("Overpass request failed", response.json()["detail"])

    def test_spatial_runtime_value_error_returns_400(self) -> None:
        self.geo_engine.analyze_buffers.side_effect = ValueError("invalid radius")

        response = self.client.post(
            "/api/v1/spatial/analyze",
            json=self.spatial_request(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "invalid radius")

    def test_recommender_endpoint_returns_ranked_candidates_and_explanations(self) -> None:
        response = self.client.post(
            "/api/v1/recommender/rank",
            json={
                "candidates": self.candidates(),
                "criteria": self.criteria(),
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["ranked_candidates"]), 2)
        self.assertEqual(payload["ranked_candidates"][0]["rank"], 1)
        self.assertTrue(
            payload["ranked_candidates"][1]["trade_off_explanation"]["summary"]
        )

    def test_recommender_endpoint_rejects_invalid_weight_sum(self) -> None:
        criteria = self.criteria()
        criteria[0]["weight"] = 0.4

        response = self.client.post(
            "/api/v1/recommender/rank",
            json={
                "candidates": self.candidates(),
                "criteria": criteria,
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("weights must sum to 1.0", str(response.json()["detail"]))

    def test_full_feasibility_endpoint_runs_all_engines(self) -> None:
        response = self.client.post(
            "/api/v1/feasibility/full",
            json={
                "business": self.business_input(),
                "selected_site": self.spatial_request(),
                "alternative_candidates": self.candidates(),
                "criteria": self.criteria(),
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("financial", payload)
        self.assertIn("risk_assessment", payload)
        self.assertIn("spatial", payload)
        self.assertIn("recommendation", payload)
        self.assertEqual(payload["spatial"]["summaries"][0]["competitor_count"], 7)
        self.assertEqual(payload["recommendation"]["ranked_candidates"][0]["rank"], 1)

    def test_full_feasibility_propagates_spatial_upstream_failure(self) -> None:
        self.geo_engine.fetch.side_effect = GeoDataError("Overpass unavailable")

        response = self.client.post(
            "/api/v1/feasibility/full",
            json={
                "business": self.business_input(),
                "selected_site": self.spatial_request(),
                "alternative_candidates": self.candidates(),
                "criteria": self.criteria(),
            },
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "Overpass unavailable")

    def test_cors_allows_only_configured_local_frontend_origin(self) -> None:
        for origin in (
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ):
            with self.subTest(origin=origin):
                allowed = self.client.options(
                    "/api/v1/financial/evaluate",
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "POST",
                    },
                )
                self.assertEqual(
                    allowed.headers.get("access-control-allow-origin"),
                    origin,
                )

        rejected = self.client.options(
            "/api/v1/financial/evaluate",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertNotIn("access-control-allow-origin", rejected.headers)


if __name__ == "__main__":
    unittest.main()
