from __future__ import annotations

from apartment_bot.core.models import DashboardRow, Listing, ListingState, ScoreResult
from apartment_bot.core.state import derive_overall_status


def build_dashboard_row(listing: Listing, score_result: ScoreResult, listing_state: ListingState) -> DashboardRow:
    return DashboardRow(
        listing_id=listing.listing_id,
        status=derive_overall_status(listing_state).value,
        address=listing.address or "",
        rent=str(listing.rent or ""),
        beds_baths=f"{listing.beds or '?'} / {listing.baths or '?'}",
        score=str(score_result.score),
        source=listing.source.value,
        listing_url=listing.listing_url,
        shane_action=listing_state.user_actions.get("shane", None).action.value if listing_state.user_actions.get("shane") else "",
        wife_action=listing_state.user_actions.get("wife", None).action.value if listing_state.user_actions.get("wife") else "",
    )


def build_more_details_message(listing: Listing, score_result: ScoreResult) -> str:
    pros = ", ".join(score_result.pros[:4]) if score_result.pros else "No standout positives extracted yet"
    cons = ", ".join(score_result.cons[:4]) if score_result.cons else "No major negatives extracted yet"
    return (
        f"{listing.address or 'Unknown address'}\n"
        f"Rent: ${listing.rent or 'N/A'} | Beds/Baths: {listing.beds or '?'} / {listing.baths or '?'} | Sqft: {listing.sqft or 'N/A'}\n"
        f"Source: {listing.source.value}\n"
        f"Top pros: {pros}\n"
        f"Top cons: {cons}\n"
        f"URL: {listing.listing_url}"
    )
