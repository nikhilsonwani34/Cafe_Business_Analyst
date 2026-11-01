"""FastAPI application for the spatial-financial decision support system."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.financial_engine import CafeAssumptions, analyze_cafe
from src.geo_engine import BoundingBox, GeoDataError, GeoEngine
from src.recommender import recommend_locations
from src.risk_engine import assess_risks
from src.schemas import (
    ErrorResponse,
    FinancialEvaluationRequest,
    FinancialEvaluationResponse,
    FinancialResult,
    FullFeasibilityRequest,
    FullFeasibilityResponse,
    RecommendationRequest,
    RecommendationResult,
    RiskAssessment,
    SpatialAnalysisRequest,
    SpatialAnalysisResponse,
)

logger = logging.getLogger(__name__)


def _default_cache_directory() -> Path:
    configured = os.getenv("SPATIAL_DSS_CACHE_DIR")
    return Path(configured) if configured else Path("data") / "cache"


app = FastAPI(
    title="Spatial-Financial Startup Feasibility DSS",
    version="0.1.0",
    description=(
        "An explainable decision support system for café feasibility. It combines "
        "deterministic financial calculations, transparent diagnostics, OpenStreetMap "
        "POI proxies, and criteria-based TOPSIS ranking; it does not predict business "
        "success with a black-box model."
    ),
)
app.state.geo_engine = GeoEngine(cache_dir=_default_cache_directory())

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def get_geo_engine(request: Request) -> GeoEngine:
    return request.app.state.geo_engine


GeoEngineDependency = Annotated[GeoEngine, Depends(get_geo_engine)]


@app.exception_handler(ValueError)
async def handle_value_error(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content=ErrorResponse(detail=str(exc)).model_dump())


@app.exception_handler(GeoDataError)
async def handle_geo_data_error(_: Request, exc: GeoDataError) -> JSONResponse:
    logger.warning("Upstream spatial analysis failed: %s", exc)
    return JSONResponse(status_code=502, content=ErrorResponse(detail=str(exc)).model_dump())


@app.exception_handler(Exception)
async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled API error",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(detail="An unexpected server error occurred").model_dump(),
    )


@app.get(
    "/health",
    tags=["health"],
    response_model=dict[str, str],
    responses={200: {"description": "Application and engines are loaded"}},
)
def health() -> dict[str, str]:
    return {"status": "healthy", "engines": "loaded"}


def _evaluate_finances(
    request: FinancialEvaluationRequest,
) -> tuple[FinancialResult, RiskAssessment]:
    business = request.business
    financial = FinancialResult.model_validate(
        analyze_cafe(CafeAssumptions(**business.model_dump()))
    )
    return financial, assess_risks(business, financial)


def _evaluate_spatial(
    request: SpatialAnalysisRequest,
    geo_engine: GeoEngine,
) -> SpatialAnalysisResponse:
    bounds = request.bounding_box
    bounding_box = BoundingBox(
        south=bounds.south,
        west=bounds.west,
        north=bounds.north,
        east=bounds.east,
    )
    dataset = geo_engine.fetch(bounding_box)
    summaries = geo_engine.analyze_buffers(
        dataset,
        request.latitude,
        request.longitude,
        request.radii_meters,
    )
    return SpatialAnalysisResponse(
        summaries=summaries,
        bounding_box=bounds,
        source=dataset.source,
        retrieved_at=dataset.retrieved_at,
        license=dataset.license,
        attribution=dataset.attribution,
        cache_status=dataset.cache_status,
    )


@app.post(
    "/api/v1/financial/evaluate",
    response_model=FinancialEvaluationResponse,
    tags=["financial"],
    responses={400: {"model": ErrorResponse}},
)
def evaluate_financial(
    request: FinancialEvaluationRequest,
) -> FinancialEvaluationResponse:
    financial, risk_assessment = _evaluate_finances(request)
    return FinancialEvaluationResponse(
        financial=financial,
        risk_assessment=risk_assessment,
    )


@app.post(
    "/api/v1/spatial/analyze",
    response_model=SpatialAnalysisResponse,
    tags=["spatial"],
    responses={
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
def analyze_spatial(
    request: SpatialAnalysisRequest,
    geo_engine: GeoEngineDependency,
) -> SpatialAnalysisResponse:
    return _evaluate_spatial(request, geo_engine)


@app.post(
    "/api/v1/recommender/rank",
    response_model=RecommendationResult,
    tags=["recommender"],
    responses={
        400: {"model": ErrorResponse},
    },
)
def rank_locations(request: RecommendationRequest) -> RecommendationResult:
    return recommend_locations(request.candidates, request.criteria)


@app.post(
    "/api/v1/feasibility/full",
    response_model=FullFeasibilityResponse,
    tags=["feasibility"],
    responses={
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
def full_feasibility(
    request: FullFeasibilityRequest,
    geo_engine: GeoEngineDependency,
) -> FullFeasibilityResponse:
    financial, risk_assessment = _evaluate_finances(
        FinancialEvaluationRequest(business=request.business)
    )
    spatial = _evaluate_spatial(request.selected_site, geo_engine)
    recommendation = recommend_locations(
        request.alternative_candidates,
        request.criteria,
    )
    return FullFeasibilityResponse(
        financial=financial,
        risk_assessment=risk_assessment,
        spatial=spatial,
        recommendation=recommendation,
    )
