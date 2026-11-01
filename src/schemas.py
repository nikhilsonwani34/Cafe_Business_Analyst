"""Validated input, output, and diagnostic contracts."""

from datetime import datetime
from enum import Enum
from math import fsum, isclose
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BusinessInput(BaseModel):
    """Operating and financial assumptions for a café scenario."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    monthly_rent: float = Field(ge=0)
    other_monthly_fixed_costs: float = Field(ge=0)
    average_ticket_size: float = Field(gt=0)
    variable_cost_per_cover: float = Field(ge=0)
    seats: int = Field(gt=0, strict=True)
    operating_hours_per_day: float = Field(gt=0)
    seat_turnovers_per_hour: float = Field(gt=0)
    operating_days_per_month: int = Field(gt=0, strict=True)
    expected_covers_per_day: float = Field(ge=0)
    initial_working_capital: float = Field(ge=0)


class FinancialResult(BaseModel):
    """Validated result contract corresponding to the financial engine output."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, from_attributes=True)

    contribution_per_cover: float
    contribution_margin_ratio: float | None
    monthly_fixed_costs: float = Field(ge=0)
    break_even_covers_per_month: float | None = Field(ge=0)
    break_even_covers_per_day: float | None = Field(ge=0)
    maximum_covers_per_day: float = Field(ge=0)
    maximum_covers_per_month: float = Field(ge=0)
    break_even_within_capacity: bool
    realized_expected_covers_per_day: float = Field(ge=0)
    projected_monthly_revenue: float = Field(ge=0)
    projected_monthly_operating_profit: float
    monthly_cash_burn: float = Field(ge=0)
    cash_runway_months: float | None = Field(ge=0)


class RiskSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class RiskRule(str, Enum):
    RENTAL_STRESS = "RENTAL_STRESS"
    CAPACITY_DEFICIT = "CAPACITY_DEFICIT"
    SHORT_RUNWAY = "SHORT_RUNWAY"
    LOW_CONTRIBUTION_MARGIN = "LOW_CONTRIBUTION_MARGIN"


class RiskFlag(BaseModel):
    """One explainable risk finding with its measured value and benchmark."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    rule_name: RiskRule
    severity: RiskSeverity
    measured_value: float | None
    threshold: float | None
    plain_language_explanation: str = Field(min_length=1)


class RiskAssessment(BaseModel):
    """All risk findings for a single business scenario."""

    model_config = ConfigDict(extra="forbid")

    flags: list[RiskFlag] = Field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(flag.severity is RiskSeverity.CRITICAL for flag in self.flags)

    @property
    def warning_count(self) -> int:
        return sum(flag.severity is RiskSeverity.WARNING for flag in self.flags)


class CandidateLocation(BaseModel):
    """A candidate location and the measured decision criteria used to rank it."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    competitor_count: int = Field(ge=0, strict=True)
    anchor_count: int = Field(ge=0, strict=True)
    avg_rent_per_sqft: float = Field(ge=0)
    accessibility_score: float = Field(ge=0, le=1)


class CriterionConfig(BaseModel):
    """A TOPSIS criterion, its relative weight, and optimization direction."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    name: Literal[
        "competitor_count",
        "anchor_count",
        "avg_rent_per_sqft",
        "accessibility_score",
    ]
    weight: float = Field(ge=0)
    is_benefit: bool = Field(strict=True)


class CriterionTradeOff(BaseModel):
    """One measured criterion on which the top candidate differs."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    criterion_name: str
    top_candidate_value: float
    compared_candidate_value: float
    weight: float = Field(ge=0)


class TradeOffExplanation(BaseModel):
    """Structured comparison of one candidate against the top-ranked option."""

    model_config = ConfigDict(extra="forbid")

    compared_candidate_id: str | None
    advantages: list[CriterionTradeOff] = Field(default_factory=list)
    disadvantages: list[CriterionTradeOff] = Field(default_factory=list)
    summary: str = Field(min_length=1)


class RankedCandidate(BaseModel):
    """A candidate's TOPSIS score and auditable intermediate calculations."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    candidate: CandidateLocation
    score: float = Field(ge=0, le=1)
    rank: int = Field(gt=0, strict=True)
    distance_to_ideal_best: float = Field(ge=0)
    distance_to_ideal_worst: float = Field(ge=0)
    normalized_weighted_values: dict[str, float]
    trade_off_explanation: TradeOffExplanation


class RecommendationResult(BaseModel):
    """TOPSIS-ranked locations and the ideal solutions used in the ranking."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    ranked_candidates: list[RankedCandidate] = Field(min_length=1)
    criteria: list[CriterionConfig] = Field(min_length=1)
    ideal_best: dict[str, float]
    ideal_worst: dict[str, float]


class GeoBoundingBoxInput(BaseModel):
    """Validated non-wrapping WGS84 bounds for a spatial POI query."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    south: float = Field(ge=-90, lt=90)
    west: float = Field(ge=-180, lt=180)
    north: float = Field(gt=-90, le=90)
    east: float = Field(gt=-180, le=180)

    @model_validator(mode="after")
    def validate_order(self) -> "GeoBoundingBoxInput":
        if self.south >= self.north:
            raise ValueError("south must be less than north")
        if self.west >= self.east:
            raise ValueError("west must be less than east")
        return self


class SpatialAnalysisRequest(BaseModel):
    """Coordinates, query bounds, and radii for an OSM spatial analysis."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    bounding_box: GeoBoundingBoxInput
    radii_meters: list[float] = Field(
        default_factory=lambda: [500.0, 1_000.0],
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_query(self) -> "SpatialAnalysisRequest":
        if any(radius <= 0 for radius in self.radii_meters):
            raise ValueError("each radius must be positive")
        if not (
            self.bounding_box.south
            <= self.latitude
            <= self.bounding_box.north
            and self.bounding_box.west
            <= self.longitude
            <= self.bounding_box.east
        ):
            raise ValueError("analysis coordinates must be within the bounding box")
        return self


class BufferSummaryResponse(BaseModel):
    """Competitor and demand-anchor counts inside one radius."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, from_attributes=True)

    radius_meters: float = Field(gt=0)
    competitor_count: int = Field(ge=0)
    demand_anchor_count: int = Field(ge=0)


class SpatialAnalysisResponse(BaseModel):
    """Spatial counts and required OSM data provenance."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    summaries: list[BufferSummaryResponse]
    bounding_box: GeoBoundingBoxInput
    source: str
    retrieved_at: datetime
    license: str
    attribution: str
    cache_status: Literal["network", "hit"]


class FinancialEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business: BusinessInput


class FinancialEvaluationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    financial: FinancialResult
    risk_assessment: RiskAssessment


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[CandidateLocation] = Field(min_length=1)
    criteria: list[CriterionConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_recommendation_inputs(self) -> "RecommendationRequest":
        _validate_recommendation_inputs(self.candidates, self.criteria)
        return self


class FullFeasibilityRequest(BaseModel):
    """Financial scenario, selected site query, and supplied alternatives."""

    model_config = ConfigDict(extra="forbid")

    business: BusinessInput
    selected_site: SpatialAnalysisRequest
    alternative_candidates: list[CandidateLocation] = Field(min_length=1)
    criteria: list[CriterionConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_recommendation_inputs(self) -> "FullFeasibilityRequest":
        _validate_recommendation_inputs(self.alternative_candidates, self.criteria)
        return self


class FullFeasibilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    financial: FinancialResult
    risk_assessment: RiskAssessment
    spatial: SpatialAnalysisResponse
    recommendation: RecommendationResult


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: str


def _validate_recommendation_inputs(
    candidates: list[CandidateLocation],
    criteria: list[CriterionConfig],
) -> None:
    candidate_ids = [candidate.id for candidate in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate ids must be unique")

    criterion_names = [criterion.name for criterion in criteria]
    if len(criterion_names) != len(set(criterion_names)):
        raise ValueError("criterion names must be unique")

    total_weight = fsum(criterion.weight for criterion in criteria)
    if not isclose(total_weight, 1.0, rel_tol=0.0, abs_tol=1e-6):
        raise ValueError("criterion weights must sum to 1.0 within 1e-6")
