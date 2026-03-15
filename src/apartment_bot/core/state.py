from __future__ import annotations

from datetime import datetime, timezone

from apartment_bot.core.models import (
    ListingState,
    OverallListingStatus,
    OutreachStatus,
    StateUpdateResult,
    UserAction,
    UserActionType,
)


def derive_overall_status(listing_state: ListingState) -> OverallListingStatus:
    actions = {entry.action for entry in listing_state.user_actions.values()}
    if any(action == UserActionType.SCHEDULE for action in actions):
        return OverallListingStatus.SCHEDULED
    if any(action == UserActionType.PASS for action in actions):
        return OverallListingStatus.PASSED
    if any(action == UserActionType.SAVE for action in actions):
        return OverallListingStatus.SAVED
    if listing_state.manual_follow_up_required:
        return OverallListingStatus.MANUAL_FOLLOW_UP
    return OverallListingStatus.NEW


def record_user_action(
    listing_state: ListingState,
    user_key: str,
    action: UserActionType,
    timestamp: datetime | None = None,
) -> StateUpdateResult:
    event_time = timestamp or datetime.now(timezone.utc)
    duplicate_schedule_blocked = False
    notify_other_user = False
    notification_message: str | None = None

    if action == UserActionType.SCHEDULE and any(
        existing.action == UserActionType.SCHEDULE for existing in listing_state.user_actions.values()
    ):
        duplicate_schedule_blocked = True
    else:
        listing_state.user_actions[user_key] = UserAction(user_key=user_key, action=action, timestamp=event_time)

    if action == UserActionType.SCHEDULE and not duplicate_schedule_blocked:
        notify_other_user = True
        notification_message = f"{user_key} requested outreach for listing {listing_state.listing_id}."

    overall_status = derive_overall_status(listing_state)
    return StateUpdateResult(
        listing_state=listing_state,
        overall_status=overall_status,
        duplicate_schedule_blocked=duplicate_schedule_blocked,
        notify_other_user=notify_other_user,
        notification_message=notification_message,
    )


def mark_outreach_sent(listing_state: ListingState, triggered_by: str, sent: bool, manual_follow_up: bool) -> ListingState:
    if sent:
        listing_state.outreach_status = OutreachStatus.SENT
    elif manual_follow_up:
        listing_state.outreach_status = OutreachStatus.NEEDS_MANUAL_FOLLOW_UP
        listing_state.manual_follow_up_required = True
    else:
        listing_state.outreach_status = OutreachStatus.BLOCKED_DUPLICATE
    listing_state.outreach_triggered_by = triggered_by
    listing_state.outreach_timestamp = datetime.now(timezone.utc)
    return listing_state
