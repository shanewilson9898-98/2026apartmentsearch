from __future__ import annotations

from dataclasses import dataclass

from apartment_bot.core.models import Listing


@dataclass(frozen=True)
class OutreachResult:
    sent: bool
    manual_follow_up_required: bool
    message: str


class OutreachService:
    def send_tour_request(self, listing: Listing, triggered_by_user: str) -> OutreachResult:
        if listing.contact_phone or listing.contact_email:
            # TODO: Route outreach through the source-specific contact path once available.
            # TODO: Add per-source delivery logic rather than assuming SMS/email parity.
            return OutreachResult(
                sent=False,
                manual_follow_up_required=True,
                message="Contact path exists but automated sending is not wired yet.",
            )

        return OutreachResult(
            sent=False,
            manual_follow_up_required=True,
            message="No sendable contact path available; manual follow-up required.",
        )
