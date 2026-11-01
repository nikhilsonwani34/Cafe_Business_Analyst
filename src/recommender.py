"""Explainable TOPSIS ranking for candidate business locations."""

from __future__ import annotations

from math import fsum, hypot, isclose
from typing import Sequence

from src.schemas import (
    CandidateLocation,
    CriterionConfig,
    CriterionTradeOff,
    RankedCandidate,
    RecommendationResult,
    TradeOffExplanation,
)

WEIGHT_SUM_TOLERANCE = 1e-6


def recommend_locations(
    candidates: Sequence[CandidateLocation],
    criteria: Sequence[CriterionConfig],
) -> RecommendationResult:
    """Rank candidate locations using vector-normalized weighted TOPSIS.

    Criteria weights must sum to 1 within ``WEIGHT_SUM_TOLERANCE``. If a
    criterion's vector norm is zero, its normalized values are all zero. When
    all candidate distances to both ideal solutions are zero (one candidate
    or identical candidate rows), each candidate receives a neutral score of
    0.5. Tied scores retain input order.
    """
    candidate_list = list(candidates)
    criterion_list = list(criteria)
    _validate_inputs(candidate_list, criterion_list)

    criterion_names = [criterion.name for criterion in criterion_list]
    raw_columns: dict[str, list[float]] = {}
    for name in criterion_names:
        try:
            raw_columns[name] = [
                float(getattr(candidate, name)) for candidate in candidate_list
            ]
        except OverflowError as exc:
            raise ValueError(
                f"criterion {name!r} contains a value outside the supported "
                "numeric range"
            ) from exc
    norms = {
        name: hypot(*values)
        for name, values in raw_columns.items()
    }
    weights = {criterion.name: criterion.weight for criterion in criterion_list}

    weighted_rows: list[dict[str, float]] = []
    for row_index in range(len(candidate_list)):
        weighted_rows.append(
            {
                name: (
                    raw_columns[name][row_index] / norms[name] * weights[name]
                    if norms[name] > 0
                    else 0.0
                )
                for name in criterion_names
            }
        )

    ideal_best: dict[str, float] = {}
    ideal_worst: dict[str, float] = {}
    for criterion in criterion_list:
        values = [row[criterion.name] for row in weighted_rows]
        if criterion.is_benefit:
            ideal_best[criterion.name] = max(values)
            ideal_worst[criterion.name] = min(values)
        else:
            ideal_best[criterion.name] = min(values)
            ideal_worst[criterion.name] = max(values)

    separations = [
        (
            _euclidean_distance(row, ideal_best, criterion_names),
            _euclidean_distance(row, ideal_worst, criterion_names),
        )
        for row in weighted_rows
    ]
    scores = [
        (distance_worst / (distance_best + distance_worst))
        if distance_best + distance_worst > 0
        else 0.5
        for distance_best, distance_worst in separations
    ]

    sorted_indices = sorted(
        range(len(candidate_list)),
        key=lambda index: (-scores[index], index),
    )
    winner_index = sorted_indices[0]
    ranked: list[RankedCandidate] = []
    for rank, candidate_index in enumerate(sorted_indices, start=1):
        candidate = candidate_list[candidate_index]
        distance_best, distance_worst = separations[candidate_index]
        explanation = _build_trade_off_explanation(
            winner=candidate_list[winner_index],
            compared=candidate,
            is_winner=candidate_index == winner_index,
            winner_score=scores[winner_index],
            compared_score=scores[candidate_index],
            criteria=criterion_list,
        )
        ranked.append(
            RankedCandidate(
                candidate=candidate,
                score=scores[candidate_index],
                rank=rank,
                distance_to_ideal_best=distance_best,
                distance_to_ideal_worst=distance_worst,
                normalized_weighted_values=weighted_rows[candidate_index],
                trade_off_explanation=explanation,
            )
        )

    return RecommendationResult(
        ranked_candidates=ranked,
        criteria=criterion_list,
        ideal_best=ideal_best,
        ideal_worst=ideal_worst,
    )


def _validate_inputs(
    candidates: list[CandidateLocation],
    criteria: list[CriterionConfig],
) -> None:
    if not candidates:
        raise ValueError("at least one candidate location is required")
    if not criteria:
        raise ValueError("at least one criterion is required")

    candidate_ids = [candidate.id for candidate in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate ids must be unique")

    criterion_names = [criterion.name for criterion in criteria]
    if len(criterion_names) != len(set(criterion_names)):
        raise ValueError("criterion names must be unique")

    total_weight = fsum(criterion.weight for criterion in criteria)
    if not isclose(
        total_weight,
        1.0,
        rel_tol=0.0,
        abs_tol=WEIGHT_SUM_TOLERANCE,
    ):
        raise ValueError(
            f"criterion weights must sum to 1.0 "
            f"(received {total_weight:.12g}; tolerance {WEIGHT_SUM_TOLERANCE:g})"
        )


def _euclidean_distance(
    point: dict[str, float],
    ideal: dict[str, float],
    criterion_names: list[str],
) -> float:
    return hypot(*(point[name] - ideal[name] for name in criterion_names))


def _build_trade_off_explanation(
    *,
    winner: CandidateLocation,
    compared: CandidateLocation,
    is_winner: bool,
    winner_score: float,
    compared_score: float,
    criteria: list[CriterionConfig],
) -> TradeOffExplanation:
    if is_winner:
        return TradeOffExplanation(
            compared_candidate_id=None,
            summary="Top-ranked candidate; no comparison is applicable.",
        )

    advantages: list[CriterionTradeOff] = []
    disadvantages: list[CriterionTradeOff] = []
    for criterion in criteria:
        winner_value = float(getattr(winner, criterion.name))
        compared_value = float(getattr(compared, criterion.name))
        if winner_value == compared_value:
            continue

        difference = CriterionTradeOff(
            criterion_name=criterion.name,
            top_candidate_value=winner_value,
            compared_candidate_value=compared_value,
            weight=criterion.weight,
        )
        winner_is_better = (
            winner_value > compared_value
            if criterion.is_benefit
            else winner_value < compared_value
        )
        if winner_is_better:
            advantages.append(difference)
        else:
            disadvantages.append(difference)

    reason = (
        f"{winner.name} ranks above {compared.name} with a TOPSIS score of "
        f"{winner_score:.4f} versus {compared_score:.4f}."
    )
    if advantages:
        reason += " It performs better on " + ", ".join(
            f"{item.criterion_name} ({item.top_candidate_value:g} vs "
            f"{item.compared_candidate_value:g}; weight {item.weight:g})"
            for item in advantages
        ) + "."
    if disadvantages:
        reason += " It performs worse on " + ", ".join(
            f"{item.criterion_name} ({item.top_candidate_value:g} vs "
            f"{item.compared_candidate_value:g}; weight {item.weight:g})"
            for item in disadvantages
        ) + "."
    if not advantages and not disadvantages:
        reason += " Both candidates have identical values for the selected criteria."

    return TradeOffExplanation(
        compared_candidate_id=compared.id,
        advantages=advantages,
        disadvantages=disadvantages,
        summary=reason,
    )
