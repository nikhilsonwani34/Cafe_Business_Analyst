"""OpenStreetMap POI retrieval, local caching, and buffer analysis."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

import requests

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT_SECONDS = 30.0
CACHE_TTL_SECONDS = 86_400.0
EARTH_RADIUS_METERS = 6_371_008.8
CACHE_FORMAT_VERSION = 1
OSM_ATTRIBUTION = "© OpenStreetMap contributors"
OSM_LICENSE = "ODbL-1.0"


class GeoDataError(RuntimeError):
    """Raised when POI data cannot be retrieved, parsed, or cached safely."""


class POICategory(str, Enum):
    COMPETITOR = "competitor"
    DEMAND_ANCHOR = "demand_anchor"


@dataclass(frozen=True)
class BoundingBox:
    """A non-wrapping geographic bounding box in WGS84 coordinates."""

    south: float
    west: float
    north: float
    east: float

    def __post_init__(self) -> None:
        values = (self.south, self.west, self.north, self.east)
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in values
        ):
            raise ValueError("bounding-box coordinates must be finite numbers")
        if not -90 <= self.south < self.north <= 90:
            raise ValueError("latitude bounds must satisfy -90 <= south < north <= 90")
        if not -180 <= self.west < self.east <= 180:
            raise ValueError("longitude bounds must satisfy -180 <= west < east <= 180")

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.south, self.west, self.north, self.east)


@dataclass(frozen=True)
class PointOfInterest:
    osm_type: str
    osm_id: int
    name: str | None
    latitude: float
    longitude: float
    categories: tuple[POICategory, ...]
    tags: Mapping[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.osm_type, str) or self.osm_type not in {
            "node",
            "way",
            "relation",
        }:
            raise ValueError("osm_type must be node, way, or relation")
        if isinstance(self.osm_id, bool) or not isinstance(self.osm_id, int) or self.osm_id < 0:
            raise ValueError("osm_id must be a non-negative integer")
        _validate_coordinate(self.latitude, self.longitude, "POI")
        if self.name is not None and not isinstance(self.name, str):
            raise ValueError("POI name must be a string or None")
        if not self.categories:
            raise ValueError("a POI must have at least one recognized category")
        if any(not isinstance(category, POICategory) for category in self.categories):
            raise ValueError("POI categories must use POICategory values")
        if not isinstance(self.tags, Mapping) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in self.tags.items()
        ):
            raise ValueError("POI tags must be a mapping of strings to strings")


@dataclass(frozen=True)
class GeoDataset:
    """POIs and provenance for one Overpass query area."""

    bounding_box: BoundingBox
    pois: tuple[PointOfInterest, ...]
    retrieved_at: datetime
    source: str = "OpenStreetMap via Overpass API"
    license: str = OSM_LICENSE
    attribution: str = OSM_ATTRIBUTION
    cache_status: str = "network"


@dataclass(frozen=True)
class BufferSummary:
    radius_meters: float
    competitor_count: int
    demand_anchor_count: int


def build_overpass_query(bounding_box: BoundingBox) -> str:
    """Build an Overpass QL query for café competitors and anchor POIs."""
    south, west, north, east = bounding_box.as_tuple()
    bounds = f"({south:.7f},{west:.7f},{north:.7f},{east:.7f})"
    return (
        "[out:json][timeout:25];\n"
        "(\n"
        f'  nwr["amenity"~"^(cafe|fast_food|restaurant|university)$"]{bounds};\n'
        f'  nwr["building"="university"]{bounds};\n'
        f'  nwr["office"]{bounds};\n'
        f'  nwr["public_transport"="station"]{bounds};\n'
        f'  nwr["railway"~"^(station|halt)$"]{bounds};\n'
        f'  nwr["station"="subway"]{bounds};\n'
        ");\n"
        "out center tags;"
    )


class GeoEngine:
    """Fetch and cache OSM POIs, then calculate distance-buffer counts."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        endpoint: str = OVERPASS_ENDPOINT,
        timeout_seconds: float = OVERPASS_TIMEOUT_SECONDS,
        cache_ttl_seconds: float = CACHE_TTL_SECONDS,
        session: requests.Session | None = None,
    ) -> None:
        if not endpoint:
            raise ValueError("endpoint must not be empty")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be finite and positive")
        if (
            isinstance(cache_ttl_seconds, bool)
            or not isinstance(cache_ttl_seconds, (int, float))
            or not math.isfinite(cache_ttl_seconds)
            or cache_ttl_seconds < 0
        ):
            raise ValueError("cache_ttl_seconds must be finite and non-negative")
        self.cache_dir = Path(cache_dir)
        self.endpoint = endpoint
        self.timeout_seconds = float(timeout_seconds)
        self.cache_ttl_seconds = float(cache_ttl_seconds)
        self.session = session if session is not None else requests.Session()

    def fetch(self, bounding_box: BoundingBox) -> GeoDataset:
        """Return a fresh cached dataset or retrieve, validate, and cache one."""
        cache_path = self._cache_path(bounding_box)
        cached = self._read_cache(cache_path, bounding_box)
        if cached is not None:
            age_seconds = (datetime.now(timezone.utc) - cached.retrieved_at).total_seconds()
            if 0 <= age_seconds <= self.cache_ttl_seconds:
                return replace(cached, cache_status="hit")

        query = build_overpass_query(bounding_box)
        try:
            response = self.session.post(
                self.endpoint,
                data={"data": query},
                timeout=self.timeout_seconds,
                headers={"User-Agent": "SpatialFinancialDSS/0.1 (OSM Overpass client)"},
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise GeoDataError(f"Overpass request failed: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise GeoDataError("Overpass returned invalid JSON") from exc

        dataset = self._parse_payload(payload, bounding_box)
        self._write_cache(cache_path, dataset)
        return dataset

    def analyze_buffers(
        self,
        dataset: GeoDataset,
        latitude: float,
        longitude: float,
        radii_meters: Sequence[float] = (500.0, 1_000.0),
    ) -> tuple[BufferSummary, ...]:
        """Count competitor and demand-anchor POIs inside each radius."""
        _validate_coordinate(latitude, longitude, "analysis location")
        if not radii_meters:
            raise ValueError("radii_meters must contain at least one radius")

        radii: list[float] = []
        for radius in radii_meters:
            if (
                isinstance(radius, bool)
                or not isinstance(radius, (int, float))
                or not math.isfinite(radius)
                or radius <= 0
            ):
                raise ValueError("each radius must be a finite, positive number")
            radii.append(float(radius))

        distances = [
            (
                poi,
                _haversine_meters(latitude, longitude, poi.latitude, poi.longitude),
            )
            for poi in dataset.pois
        ]
        return tuple(
            BufferSummary(
                radius_meters=radius,
                competitor_count=sum(
                    POICategory.COMPETITOR in poi.categories and distance <= radius
                    for poi, distance in distances
                ),
                demand_anchor_count=sum(
                    POICategory.DEMAND_ANCHOR in poi.categories and distance <= radius
                    for poi, distance in distances
                ),
            )
            for radius in radii
        )

    def _cache_path(self, bounding_box: BoundingBox) -> Path:
        cache_key = json.dumps(
            {
                "format_version": CACHE_FORMAT_VERSION,
                "endpoint": self.endpoint,
                "bounding_box": bounding_box.as_tuple(),
                "query": build_overpass_query(bounding_box),
            },
            separators=(",", ":"),
        )
        digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"osm-pois-{digest}.json"

    def _read_cache(
        self,
        cache_path: Path,
        expected_box: BoundingBox,
    ) -> GeoDataset | None:
        try:
            raw = cache_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise GeoDataError(f"Could not read POI cache {cache_path}: {exc}") from exc

        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("cache root must be an object")
            if payload.get("format_version") != CACHE_FORMAT_VERSION:
                raise ValueError("unsupported cache format version")
            dataset = self._dataset_from_json(payload["dataset"])
            if dataset.bounding_box != expected_box:
                raise ValueError("cached bounding box does not match request")
        except (KeyError, TypeError, ValueError) as exc:
            raise GeoDataError(f"POI cache is invalid: {exc}") from exc
        return dataset

    def _write_cache(self, cache_path: Path, dataset: GeoDataset) -> None:
        payload = {
            "format_version": CACHE_FORMAT_VERSION,
            "dataset": _dataset_to_json(dataset),
        }
        temporary_path = cache_path.with_name(
            f"{cache_path.name}.{uuid4().hex}.tmp"
        )
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            temporary_path.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            temporary_path.replace(cache_path)
        except OSError as exc:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                raise GeoDataError(
                    f"Could not write POI cache {cache_path}: {exc}; "
                    f"temporary-file cleanup also failed: {cleanup_error}"
                ) from cleanup_error
            raise GeoDataError(f"Could not write POI cache {cache_path}: {exc}") from exc

    @staticmethod
    def _parse_payload(payload: Any, bounding_box: BoundingBox) -> GeoDataset:
        if not isinstance(payload, dict):
            raise GeoDataError("Overpass response must be a JSON object")
        if payload.get("remark"):
            raise GeoDataError(f"Overpass reported an error: {payload['remark']}")
        if not isinstance(payload.get("elements"), list):
            raise GeoDataError("Overpass response must contain an elements array")

        pois: list[PointOfInterest] = []
        seen: set[tuple[str, int]] = set()
        try:
            for element in payload["elements"]:
                poi = _parse_element(element)
                if poi is None:
                    continue
                identity = (poi.osm_type, poi.osm_id)
                if identity not in seen:
                    seen.add(identity)
                    pois.append(poi)
        except (KeyError, TypeError, ValueError) as exc:
            raise GeoDataError(f"Overpass response contains an invalid POI: {exc}") from exc

        return GeoDataset(
            bounding_box=bounding_box,
            pois=tuple(pois),
            retrieved_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _dataset_from_json(payload: Any) -> GeoDataset:
        if not isinstance(payload, dict):
            raise ValueError("dataset must be an object")
        if not isinstance(payload.get("source"), str) or not payload["source"]:
            raise ValueError("source must be a non-empty string")
        box_values = payload["bounding_box"]
        if not isinstance(box_values, list) or len(box_values) != 4:
            raise ValueError("bounding_box must contain four coordinates")
        box = BoundingBox(*box_values)
        pois_payload = payload["pois"]
        if not isinstance(pois_payload, list):
            raise ValueError("pois must be an array")
        pois = tuple(_poi_from_json(item) for item in pois_payload)
        retrieved_at = datetime.fromisoformat(payload["retrieved_at"])
        if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
            raise ValueError("retrieved_at must include a timezone")
        if payload["license"] != OSM_LICENSE or payload["attribution"] != OSM_ATTRIBUTION:
            raise ValueError("cache is missing required OSM license attribution")
        return GeoDataset(
            bounding_box=box,
            pois=pois,
            retrieved_at=retrieved_at.astimezone(timezone.utc),
            source=payload["source"],
            license=payload["license"],
            attribution=payload["attribution"],
            cache_status="hit",
        )


def _parse_element(element: Any) -> PointOfInterest | None:
    if not isinstance(element, dict):
        raise ValueError("element must be an object")
    osm_type = element.get("type")
    osm_id = element.get("id")
    if osm_type not in {"node", "way", "relation"}:
        raise ValueError("element has an invalid OSM type")
    if isinstance(osm_id, bool) or not isinstance(osm_id, int) or osm_id < 0:
        raise ValueError("element has an invalid OSM id")
    tags = element.get("tags", {})
    if not isinstance(tags, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in tags.items()
    ):
        raise ValueError("element tags must be strings")

    categories: list[POICategory] = []
    if tags.get("amenity") in {"cafe", "fast_food", "restaurant"}:
        categories.append(POICategory.COMPETITOR)
    if (
        tags.get("amenity") == "university"
        or tags.get("building") == "university"
        or "office" in tags
        or tags.get("public_transport") == "station"
        or tags.get("railway") in {"station", "halt"}
        or tags.get("station") == "subway"
    ):
        categories.append(POICategory.DEMAND_ANCHOR)
    if not categories:
        return None

    center = element.get("center", {})
    if not isinstance(center, dict):
        raise ValueError("element center must be an object")
    latitude = element.get("lat", center.get("lat"))
    longitude = element.get("lon", center.get("lon"))
    if latitude is None or longitude is None:
        raise ValueError("recognized POI has no point or center coordinates")
    _validate_coordinate(latitude, longitude, "POI")

    name = tags.get("name")
    return PointOfInterest(
        osm_type=osm_type,
        osm_id=osm_id,
        name=name,
        latitude=float(latitude),
        longitude=float(longitude),
        categories=tuple(categories),
        tags=dict(tags),
    )


def _poi_from_json(payload: Any) -> PointOfInterest:
    if not isinstance(payload, dict):
        raise ValueError("cached POI must be an object")
    return PointOfInterest(
        osm_type=payload["osm_type"],
        osm_id=payload["osm_id"],
        name=payload["name"],
        latitude=payload["latitude"],
        longitude=payload["longitude"],
        categories=tuple(POICategory(value) for value in payload["categories"]),
        tags=payload["tags"],
    )


def _dataset_to_json(dataset: GeoDataset) -> dict[str, Any]:
    return {
        "bounding_box": list(dataset.bounding_box.as_tuple()),
        "pois": [
            {
                "osm_type": poi.osm_type,
                "osm_id": poi.osm_id,
                "name": poi.name,
                "latitude": poi.latitude,
                "longitude": poi.longitude,
                "categories": [category.value for category in poi.categories],
                "tags": dict(poi.tags),
            }
            for poi in dataset.pois
        ],
        "retrieved_at": dataset.retrieved_at.isoformat(),
        "source": dataset.source,
        "license": dataset.license,
        "attribution": dataset.attribution,
    }


def _validate_coordinate(latitude: float, longitude: float, label: str) -> None:
    if (
        isinstance(latitude, bool)
        or not isinstance(latitude, (int, float))
        or not math.isfinite(latitude)
        or not -90 <= latitude <= 90
        or isinstance(longitude, bool)
        or not isinstance(longitude, (int, float))
        or not math.isfinite(longitude)
        or not -180 <= longitude <= 180
    ):
        raise ValueError(f"{label} must have valid WGS84 coordinates")


def _haversine_meters(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    lat_a, lat_b = math.radians(latitude_a), math.radians(latitude_b)
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(longitude_b - longitude_a)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(min(1.0, haversine)))
