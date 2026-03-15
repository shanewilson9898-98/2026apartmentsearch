from __future__ import annotations

from apartment_bot.config import Settings
from apartment_bot.core.models import Listing, ScoreResult


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def score_listing(listing: Listing, settings: Settings) -> ScoreResult:
    score = 50.0
    pros: list[str] = []
    cons: list[str] = []

    if listing.rent is not None:
        if listing.rent <= settings.target_rent:
            score += 15
            pros.append("at or below target rent")
        else:
            rent_span = max(settings.hard_max_rent - settings.target_rent, 1)
            penalty = ((listing.rent - settings.target_rent) / rent_span) * 15
            score -= _clamp(penalty, 0, 15)
            cons.append("rent above target")

    if listing.sqft is not None and listing.sqft >= settings.preferred_min_sqft:
        score += 8
        pros.append("meets preferred square footage")

    if listing.has_parking:
        score += 8
        pros.append("parking")
    if listing.pet_friendly:
        score += 8
        pros.append("pet friendly")

    positives = [
        (listing.has_private_outdoor_space, "private outdoor space", 5),
        (listing.natural_light_signal, "good natural light", 4),
        (listing.renovated_kitchen_signal, "renovated kitchen or newer appliances", 5),
        (listing.quiet_street_signal, "quiet residential street", 4),
        (listing.caltrain_signal, "close to Caltrain", 5),
        (listing.walkability_signal, "walkable to groceries and restaurants", 5),
        (listing.has_fitness_center, "on-site fitness center", 3),
    ]
    for enabled, label, points in positives:
        if enabled:
            score += points
            pros.append(label)

    negatives = [
        (listing.street_parking_only, "street parking only", 6),
        (listing.older_interiors_signal, "older interiors", 5),
        (listing.ground_floor_signal, "ground floor unit", 4),
        (listing.unclear_availability_signal, "unclear availability date", 4),
        (listing.broker_fee_signal, "broker fee", 7),
    ]
    for enabled, label, points in negatives:
        if enabled:
            score -= points
            cons.append(label)

    if listing.completeness_score < 0.7:
        score -= 6
        cons.append("limited listing detail")

    return ScoreResult(score=round(_clamp(score, 0, 100), 1), pros=pros, cons=cons)
