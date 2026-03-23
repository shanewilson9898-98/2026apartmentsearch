from __future__ import annotations

from apartment_bot.config import Settings
from apartment_bot.core.models import FilterResult, Listing


def apply_hard_filters(listing: Listing, settings: Settings) -> FilterResult:
    reasons: list[str] = []

    if not listing.address or not listing.address.strip():
        reasons.append("missing real address")
    if listing.scam_signal:
        reasons.append("scam signal")
    if listing.completeness_score < 0.4:
        reasons.append("extremely incomplete listing")
    if listing.income_restricted_signal:
        reasons.append("income-restricted housing")
    if listing.senior_housing_signal:
        reasons.append("senior housing")
    if listing.student_housing_signal:
        reasons.append("student housing")
    if listing.beds is None or listing.beds < settings.min_beds:
        reasons.append("below minimum bedrooms")
    if listing.baths is None or listing.baths < settings.min_baths:
        reasons.append("below minimum bathrooms")
    if listing.rent is None or listing.rent > settings.hard_max_rent:
        reasons.append("rent exceeds hard max or missing")
    if not (listing.has_in_unit_laundry or listing.has_building_laundry):
        reasons.append("missing in-unit or on-site laundry")
    if not listing.has_dishwasher:
        reasons.append("missing dishwasher")

    return FilterResult(passed=not reasons, reasons=reasons)
