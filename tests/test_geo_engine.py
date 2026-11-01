from datetime import datetime, timezone
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

import requests

from src.geo_engine import (
    BoundingBox,
    GeoDataError,
    GeoEngine,
    POICategory,
    build_overpass_query,
)


class GeoEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bounding_box = BoundingBox(south=12.9, west=77.5, north=13.1, east=77.7)
        self.payload = {
            "elements": [
                {
                    "type": "node",
                    "id": 1,
                    "lat": 13.0,
                    "lon": 77.6,
                    "tags": {"amenity": "cafe", "name": "Test Café"},
                },
                {
                    "type": "way",
                    "id": 2,
                    "center": {"lat": 13.004, "lon": 77.6},
                    "tags": {"office": "company"},
                },
                {
                    "type": "relation",
                    "id": 3,
                    "center": {"lat": 13.02, "lon": 77.6},
                    "tags": {"railway": "station"},
                },
                {
                    "type": "node",
                    "id": 4,
                    "lat": 13.0,
                    "lon": 77.61,
                    "tags": {"shop": "supermarket"},
                },
            ]
        }

    def make_engine(self, cache_dir: Path, session: Mock, **kwargs) -> GeoEngine:
        return GeoEngine(
            cache_dir,
            endpoint="https://overpass.example/api/interpreter",
            session=session,
            **kwargs,
        )

    def test_builds_bounded_overpass_query_for_competitors_and_anchors(self) -> None:
        query = build_overpass_query(self.bounding_box)

        self.assertIn('nwr["amenity"~"^(cafe|fast_food|restaurant|university)$"]', query)
        self.assertIn('nwr["office"]', query)
        self.assertIn('nwr["public_transport"="station"]', query)
        self.assertIn("(12.9000000,77.5000000,13.1000000,77.7000000)", query)
        self.assertIn("out center tags", query)

    def test_fetch_parses_nodes_and_way_centers_and_records_provenance(self) -> None:
        session = Mock()
        response = Mock()
        response.json.return_value = self.payload
        session.post.return_value = response

        with TemporaryDirectory() as directory:
            dataset = self.make_engine(Path(directory), session).fetch(self.bounding_box)

        self.assertEqual(len(dataset.pois), 3)
        self.assertEqual(dataset.pois[0].categories, (POICategory.COMPETITOR,))
        self.assertEqual(dataset.pois[1].latitude, 13.004)
        self.assertEqual(dataset.pois[1].categories, (POICategory.DEMAND_ANCHOR,))
        self.assertEqual(dataset.source, "OpenStreetMap via Overpass API")
        self.assertEqual(dataset.license, "ODbL-1.0")
        self.assertEqual(dataset.attribution, "© OpenStreetMap contributors")
        self.assertEqual(dataset.cache_status, "network")
        session.post.assert_called_once()

    def test_fresh_cache_avoids_network_and_preserves_metadata(self) -> None:
        session = Mock()
        response = Mock()
        response.json.return_value = self.payload
        session.post.return_value = response

        with TemporaryDirectory() as directory:
            engine = self.make_engine(Path(directory), session)
            first = engine.fetch(self.bounding_box)
            cached = engine.fetch(self.bounding_box)

        self.assertEqual(first.pois, cached.pois)
        self.assertEqual(cached.retrieved_at, first.retrieved_at)
        self.assertEqual(cached.cache_status, "hit")
        session.post.assert_called_once()

    def test_expired_cache_is_refreshed_from_overpass(self) -> None:
        session = Mock()
        response = Mock()
        response.json.return_value = self.payload
        session.post.return_value = response

        with TemporaryDirectory() as directory:
            engine = self.make_engine(Path(directory), session, cache_ttl_seconds=0)
            engine.fetch(self.bounding_box)
            refreshed = engine.fetch(self.bounding_box)

        self.assertEqual(refreshed.cache_status, "network")
        self.assertEqual(session.post.call_count, 2)

    def test_counts_pois_within_radius_and_includes_exact_boundary(self) -> None:
        boundary_latitude = math.degrees(500 / 6_371_008.8)
        payload = {
            "elements": [
                {
                    "type": "node",
                    "id": 1,
                    "lat": 0,
                    "lon": 0,
                    "tags": {"amenity": "cafe"},
                },
                {
                    "type": "node",
                    "id": 2,
                    "lat": boundary_latitude,
                    "lon": 0,
                    "tags": {"amenity": "cafe"},
                },
            ]
        }
        session = Mock()
        response = Mock()
        response.json.return_value = payload
        session.post.return_value = response

        with TemporaryDirectory() as directory:
            engine = self.make_engine(Path(directory), session)
            equatorial_box = BoundingBox(south=-1, west=-1, north=1, east=1)
            dataset = engine.fetch(equatorial_box)
            summaries = engine.analyze_buffers(
                dataset,
                0,
                0,
                radii_meters=(500, 500.01),
            )

        self.assertEqual(summaries[0].competitor_count, 2)
        self.assertEqual(summaries[1].competitor_count, 2)

    def test_refresh_failure_does_not_return_expired_cache_silently(self) -> None:
        session = Mock()
        response = Mock()
        response.json.return_value = self.payload
        session.post.return_value = response

        with TemporaryDirectory() as directory:
            engine = self.make_engine(Path(directory), session, cache_ttl_seconds=0)
            engine.fetch(self.bounding_box)
            session.post.side_effect = requests.Timeout("request timed out")

            with self.assertRaisesRegex(GeoDataError, "Overpass request failed"):
                engine.fetch(self.bounding_box)

    def test_overpass_remark_is_reported_as_an_error(self) -> None:
        session = Mock()
        response = Mock()
        response.json.return_value = {
            "remark": "query timed out",
        }
        session.post.return_value = response

        with TemporaryDirectory() as directory:
            engine = self.make_engine(Path(directory), session)
            with self.assertRaisesRegex(GeoDataError, "query timed out"):
                engine.fetch(self.bounding_box)

    def test_rejects_invalid_bounding_boxes(self) -> None:
        with self.assertRaisesRegex(ValueError, "latitude bounds"):
            BoundingBox(south=13, west=77, north=12, east=78)
        with self.assertRaisesRegex(ValueError, "longitude bounds"):
            BoundingBox(south=12, west=78, north=13, east=77)
        with self.assertRaisesRegex(ValueError, "finite numbers"):
            BoundingBox(south=float("nan"), west=77, north=13, east=78)

    def test_rejects_invalid_buffer_inputs(self) -> None:
        session = Mock()
        response = Mock()
        response.json.return_value = {"elements": []}
        session.post.return_value = response

        with TemporaryDirectory() as directory:
            engine = self.make_engine(Path(directory), session)
            dataset = engine.fetch(self.bounding_box)
            for args, message in (
                ((91, 77.6, (500,)), "analysis location"),
                ((13, 77.6, (0,)), "radius"),
                ((13, 77.6, (float("inf"),)), "radius"),
                ((13, 77.6, ()), "at least one"),
            ):
                with self.subTest(args=args), self.assertRaisesRegex(ValueError, message):
                    engine.analyze_buffers(dataset, *args)

    def test_overpass_request_errors_are_explicit(self) -> None:
        session = Mock()
        session.post.side_effect = requests.Timeout("request timed out")

        with TemporaryDirectory() as directory:
            engine = self.make_engine(Path(directory), session)
            with self.assertRaisesRegex(GeoDataError, "Overpass request failed"):
                engine.fetch(self.bounding_box)

    def test_invalid_response_and_missing_poi_coordinates_are_rejected(self) -> None:
        session = Mock()
        response = Mock()
        response.json.return_value = {"elements": [{"type": "node"}]}
        session.post.return_value = response

        with TemporaryDirectory() as directory:
            engine = self.make_engine(Path(directory), session)
            with self.assertRaisesRegex(GeoDataError, "invalid POI"):
                engine.fetch(self.bounding_box)

        response.json.return_value = {"unexpected": []}
        session = Mock()
        session.post.return_value = response
        with TemporaryDirectory() as directory:
            engine = self.make_engine(Path(directory), session)
            with self.assertRaisesRegex(GeoDataError, "elements array"):
                engine.fetch(self.bounding_box)

    def test_corrupt_cache_fails_explicitly_instead_of_silently_ignoring(self) -> None:
        session = Mock()
        response = Mock()
        response.json.return_value = self.payload
        session.post.return_value = response

        with TemporaryDirectory() as directory:
            engine = self.make_engine(Path(directory), session)
            engine.fetch(self.bounding_box)
            cache_path = engine._cache_path(self.bounding_box)
            cache_path.write_text("{invalid json", encoding="utf-8")

            with self.assertRaisesRegex(GeoDataError, "POI cache is invalid"):
                engine.fetch(self.bounding_box)

    def test_rejects_invalid_engine_configuration(self) -> None:
        with TemporaryDirectory() as directory:
            for kwargs, message in (
                ({"timeout_seconds": 0}, "timeout_seconds"),
                ({"cache_ttl_seconds": -1}, "cache_ttl_seconds"),
                ({"endpoint": ""}, "endpoint"),
            ):
                with self.subTest(kwargs=kwargs), self.assertRaisesRegex(
                    ValueError, message
                ):
                    GeoEngine(Path(directory), **kwargs)


if __name__ == "__main__":
    unittest.main()
