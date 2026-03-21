from __future__ import annotations

from apartment_bot.core.models import Listing, ListingState, UserActionType
from apartment_bot.core.presentation import build_more_details_message
from apartment_bot.core.scoring import score_listing
from apartment_bot.core.state import derive_overall_status, is_terminal_status, mark_outreach_sent, record_user_action
from apartment_bot.integrations.outreach import OutreachService


def handle_user_reply(
    listing: Listing,
    listing_state: ListingState,
    user_key: str,
    normalized_command: str,
    action: UserActionType,
    outreach_service: OutreachService,
    settings,
) -> dict[str, str | bool]:
    if normalized_command in {"4", "more"}:
        return {"message": build_more_details_message(listing, score_listing(listing, settings)), "success": True}

    update = record_user_action(listing_state, user_key=user_key, action=action)
    response = {
        "success": not update.duplicate_schedule_blocked,
        "status": update.overall_status.value,
        "message": "Action saved.",
    }

    if update.duplicate_schedule_blocked:
        response["message"] = "Outreach already requested for this listing."
        return response

    if action == UserActionType.SCHEDULE:
        outreach_result = outreach_service.send_tour_request(listing, user_key)
        mark_outreach_sent(
            listing_state,
            triggered_by=user_key,
            sent=outreach_result.sent,
            manual_follow_up=outreach_result.manual_follow_up_required,
        )
        response["message"] = outreach_result.message
    else:
        status = derive_overall_status(listing_state)
        if status == status.MUTUAL_SAVE:
            response["message"] = "Mutual save recorded."
        elif status == status.SAVED_BY_ONE:
            response["message"] = "Saved. Waiting on the other person's decision."
        elif status == status.PASSED:
            response["message"] = "Passed."

    response["is_terminal"] = is_terminal_status(derive_overall_status(listing_state))

    return response
