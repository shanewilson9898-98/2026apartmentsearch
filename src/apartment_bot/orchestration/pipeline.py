from __future__ import annotations

from dataclasses import dataclass

from apartment_bot.config import Settings
from apartment_bot.core.decisioning import decide_score_band
from apartment_bot.core.filtering import apply_hard_filters
from apartment_bot.core.models import (
    DecisionResult,
    GeoDataset,
    GeoQualificationResult,
    Listing,
    ListingState,
    ScoreResult,
)
from apartment_bot.core.presentation import build_dashboard_row
from apartment_bot.core.scoring import score_listing
from apartment_bot.geo.loader import load_geo_dataset
from apartment_bot.geo.logic import qualify_geography


@dataclass(frozen=True)
class ListingEvaluation:
    listing: Listing
    geo_result: GeoQualificationResult
    filter_passed: bool
    filter_reasons: list[str]
    score_result: ScoreResult | None
    decision_result: DecisionResult | None


def evaluate_listing(listing: Listing, settings: Settings, geo: GeoDataset | None = None) -> ListingEvaluation:
    geo_dataset = geo or load_geo_dataset(settings.geo_data_dir)
    geo_result = qualify_geography(listing, geo_dataset, settings)
    filter_result = apply_hard_filters(listing, settings)

    if not geo_result.qualifies or not filter_result.passed:
        return ListingEvaluation(
            listing=listing,
            geo_result=geo_result,
            filter_passed=filter_result.passed,
            filter_reasons=filter_result.reasons,
            score_result=None,
            decision_result=None,
        )

    score_result = score_listing(listing, settings)
    decision_result = decide_score_band(score_result.score, settings)
    return ListingEvaluation(
        listing=listing,
        geo_result=geo_result,
        filter_passed=True,
        filter_reasons=[],
        score_result=score_result,
        decision_result=decision_result,
    )


def dashboard_row_for_listing(listing: Listing, listing_state: ListingState, settings: Settings):
    evaluation = evaluate_listing(listing, settings)
    if evaluation.score_result is None:
        return None
    return build_dashboard_row(listing, evaluation.score_result, listing_state)
