import math
import unittest

from pydantic import ValidationError

from src.recommender import WEIGHT_SUM_TOLERANCE, recommend_locations
from src.schemas import CandidateLocation, CriterionConfig


class RecommenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.criteria = [
            CriterionConfig(
                name="anchor_count",
                weight=0.5,
                is_benefit=True,
            ),
            CriterionConfig(
                name="avg_rent_per_sqft",
                weight=0.5,
                is_benefit=False,
            ),
        ]
        self.candidates = [
            self.candidate("low", "Low option", anchors=1, rent=4),
            self.candidate("middle", "Middle option", anchors=3, rent=3),
            self.candidate("high", "High option", anchors=4, rent=1),
        ]

    @staticmethod
    def candidate(
        candidate_id: str,
        name: str,
        *,
        anchors: int = 0,
        rent: float = 0,
        competitors: int = 0,
        accessibility: float = 0.5,
    ) -> CandidateLocation:
        return CandidateLocation(
            id=candidate_id,
            name=name,
            lat=12.9,
            lon=77.6,
            competitor_count=competitors,
            anchor_count=anchors,
            avg_rent_per_sqft=rent,
            accessibility_score=accessibility,
        )

    def test_hand_calculated_normalization_distances_and_scores(self) -> None:
        result = recommend_locations(self.candidates, self.criteria)

        # Each raw column has norm sqrt(1^2 + 3^2 + 4^2) = sqrt(26).
        normalization = math.sqrt(26)
        low, middle, high = result.ranked_candidates[2], result.ranked_candidates[1], result.ranked_candidates[0]
        self.assertAlmostEqual(
            low.normalized_weighted_values["anchor_count"],
            1 / (2 * normalization),
        )
        self.assertAlmostEqual(
            low.normalized_weighted_values["avg_rent_per_sqft"],
            4 / (2 * normalization),
        )
        self.assertAlmostEqual(
            result.ideal_best["anchor_count"],
            4 / (2 * normalization),
        )
        self.assertAlmostEqual(
            result.ideal_best["avg_rent_per_sqft"],
            1 / (2 * normalization),
        )
        self.assertAlmostEqual(
            low.distance_to_ideal_best,
            math.sqrt(18) / (2 * normalization),
        )
        self.assertAlmostEqual(
            low.distance_to_ideal_worst,
            0,
        )
        self.assertAlmostEqual(middle.distance_to_ideal_best, math.sqrt(5) / (2 * normalization))
        self.assertAlmostEqual(middle.distance_to_ideal_worst, math.sqrt(5) / (2 * normalization))
        self.assertAlmostEqual(high.distance_to_ideal_best, 0)
        self.assertAlmostEqual(high.distance_to_ideal_worst, math.sqrt(18) / (2 * normalization))
        self.assertAlmostEqual(high.score, 1.0)
        self.assertAlmostEqual(middle.score, 0.5)
        self.assertAlmostEqual(low.score, 0.0)
        self.assertEqual(
            [candidate.candidate.id for candidate in result.ranked_candidates],
            ["high", "middle", "low"],
        )

    def test_benefit_and_cost_directions_change_candidate_ranking(self) -> None:
        locations = [
            self.candidate("more-anchors", "More anchors", anchors=10, rent=20),
            self.candidate("less-rent", "Less rent", anchors=1, rent=2),
        ]
        anchor_result = recommend_locations(
            locations,
            [CriterionConfig(name="anchor_count", weight=1, is_benefit=True)],
        )
        rent_result = recommend_locations(
            locations,
            [CriterionConfig(name="avg_rent_per_sqft", weight=1, is_benefit=False)],
        )

        self.assertEqual(anchor_result.ranked_candidates[0].candidate.id, "more-anchors")
        self.assertEqual(rent_result.ranked_candidates[0].candidate.id, "less-rent")
        self.assertGreater(
            anchor_result.ranked_candidates[0].score,
            anchor_result.ranked_candidates[1].score,
        )
        self.assertGreater(
            rent_result.ranked_candidates[0].score,
            rent_result.ranked_candidates[1].score,
        )

    def test_zero_weight_criterion_does_not_affect_scores(self) -> None:
        result = recommend_locations(
            [
                self.candidate("many-anchors", "Many anchors", anchors=10, rent=2),
                self.candidate("few-anchors", "Few anchors", anchors=1, rent=2),
            ],
            [
                CriterionConfig(name="anchor_count", weight=1, is_benefit=True),
                CriterionConfig(name="avg_rent_per_sqft", weight=0, is_benefit=False),
            ],
        )

        self.assertEqual(result.ranked_candidates[0].candidate.id, "many-anchors")

    def test_single_candidate_receives_neutral_score_and_first_rank(self) -> None:
        result = recommend_locations([self.candidates[0]], self.criteria)

        ranked = result.ranked_candidates[0]
        self.assertEqual(ranked.rank, 1)
        self.assertEqual(ranked.score, 0.5)
        self.assertEqual(ranked.distance_to_ideal_best, 0)
        self.assertEqual(ranked.distance_to_ideal_worst, 0)
        self.assertIsNone(ranked.trade_off_explanation.compared_candidate_id)

    def test_identical_candidate_rows_receive_tied_neutral_scores(self) -> None:
        same_one = self.candidate("one", "Same location", anchors=5, rent=8)
        same_two = self.candidate("two", "Same location", anchors=5, rent=8)

        result = recommend_locations([same_one, same_two], self.criteria)

        self.assertEqual([item.score for item in result.ranked_candidates], [0.5, 0.5])
        self.assertEqual([item.rank for item in result.ranked_candidates], [1, 2])
        self.assertEqual(
            [item.candidate.id for item in result.ranked_candidates],
            ["one", "two"],
        )

    def test_zero_norm_criterion_does_not_divide_by_zero(self) -> None:
        candidates = [
            self.candidate("one", "One", anchors=0, rent=5),
            self.candidate("two", "Two", anchors=0, rent=10),
        ]
        result = recommend_locations(
            candidates,
            [
                CriterionConfig(name="anchor_count", weight=0.5, is_benefit=True),
                CriterionConfig(name="avg_rent_per_sqft", weight=0.5, is_benefit=False),
            ],
        )

        self.assertTrue(
            all(
                item.normalized_weighted_values["anchor_count"] == 0
                for item in result.ranked_candidates
            )
        )
        self.assertEqual(result.ranked_candidates[0].candidate.id, "one")

    def test_large_finite_metrics_do_not_overflow_normalization(self) -> None:
        candidates = [
            self.candidate("large", "Large", rent=1e308),
            self.candidate("small", "Small", rent=5e307),
        ]
        result = recommend_locations(
            candidates,
            [CriterionConfig(name="avg_rent_per_sqft", weight=1, is_benefit=False)],
        )

        self.assertEqual(result.ranked_candidates[0].candidate.id, "small")
        self.assertTrue(
            all(math.isfinite(item.score) for item in result.ranked_candidates)
        )

    def test_empty_candidates_and_criteria_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one candidate"):
            recommend_locations([], self.criteria)
        with self.assertRaisesRegex(ValueError, "at least one criterion"):
            recommend_locations(self.candidates, [])

    def test_invalid_weight_sum_is_rejected(self) -> None:
        criteria = [
            CriterionConfig(name="anchor_count", weight=0.4, is_benefit=True),
            CriterionConfig(name="avg_rent_per_sqft", weight=0.4, is_benefit=False),
        ]
        with self.assertRaisesRegex(ValueError, "weights must sum to 1.0"):
            recommend_locations(self.candidates, criteria)

    def test_negative_or_non_finite_weights_are_rejected_by_schema(self) -> None:
        for weight in (-0.1, float("nan"), float("inf")):
            with self.subTest(weight=weight), self.assertRaises(ValidationError):
                CriterionConfig(
                    name="anchor_count",
                    weight=weight,
                    is_benefit=True,
                )

    def test_weight_sum_within_tolerance_is_accepted(self) -> None:
        criteria = [
            CriterionConfig(name="anchor_count", weight=0.5, is_benefit=True),
            CriterionConfig(
                name="avg_rent_per_sqft",
                weight=0.5 + WEIGHT_SUM_TOLERANCE / 2,
                is_benefit=False,
            ),
        ]
        result = recommend_locations(self.candidates, criteria)

        self.assertEqual(len(result.ranked_candidates), 3)

    def test_duplicate_candidate_ids_and_criteria_are_rejected(self) -> None:
        duplicate = self.candidate("low", "Duplicate", anchors=2, rent=3)
        with self.assertRaisesRegex(ValueError, "candidate ids must be unique"):
            recommend_locations([self.candidates[0], duplicate], self.criteria)

        with self.assertRaisesRegex(ValidationError, "name"):
            CriterionConfig(name="unknown_metric", weight=1, is_benefit=True)

        duplicate_criteria = [
            CriterionConfig(name="anchor_count", weight=0.5, is_benefit=True),
            CriterionConfig(name="anchor_count", weight=0.5, is_benefit=True),
        ]
        with self.assertRaisesRegex(ValueError, "criterion names must be unique"):
            recommend_locations(self.candidates, duplicate_criteria)

    def test_candidate_schema_rejects_invalid_measurements(self) -> None:
        invalid_values = (
            {"avg_rent_per_sqft": -1},
            {"competitor_count": -1},
            {"accessibility_score": 1.1},
            {"lat": 91},
            {"lon": -181},
        )
        base = self.candidates[0].model_dump()
        for invalid in invalid_values:
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                CandidateLocation.model_validate({**base, **invalid})

    def test_trade_off_explanations_compare_top_candidate_to_others(self) -> None:
        result = recommend_locations(self.candidates, self.criteria)

        locations = [
            self.candidate("anchor-rich", "Anchor-rich", anchors=10, rent=10),
            self.candidate("lower-rent", "Lower-rent", anchors=5, rent=1),
        ]
        result = recommend_locations(
            locations,
            [
                CriterionConfig(name="anchor_count", weight=0.8, is_benefit=True),
                CriterionConfig(
                    name="avg_rent_per_sqft",
                    weight=0.2,
                    is_benefit=False,
                ),
            ],
        )

        winner, lower = result.ranked_candidates
        explanation = lower.trade_off_explanation
        self.assertEqual(winner.candidate.id, "anchor-rich")
        self.assertEqual(explanation.compared_candidate_id, "lower-rent")
        self.assertEqual(
            [item.criterion_name for item in explanation.advantages],
            ["anchor_count"],
        )
        self.assertEqual(
            [item.criterion_name for item in explanation.disadvantages],
            ["avg_rent_per_sqft"],
        )
        self.assertIn("ranks above Lower-rent", explanation.summary)
        self.assertIn("anchor_count", explanation.summary)
        self.assertIn("avg_rent_per_sqft", explanation.summary)


if __name__ == "__main__":
    unittest.main()
