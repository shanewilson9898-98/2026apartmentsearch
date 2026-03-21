from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from apartment_bot.adapters.craigslist import CraigslistAdapter
from apartment_bot.config import Settings
from apartment_bot.core.models import OverallListingStatus
from apartment_bot.core.normalize import normalize_phone
from apartment_bot.core.presentation import build_dashboard_row
from apartment_bot.core.scoring import score_listing
from apartment_bot.core.sms import parse_sms_command
from apartment_bot.core.state import derive_overall_status, is_terminal_status
from apartment_bot.core.store import JsonStateStore
from apartment_bot.integrations.outreach import OutreachService
from apartment_bot.orchestration.handlers import handle_user_reply
from apartment_bot.orchestration.pipeline import evaluate_listing
from apartment_bot.orchestration.sample_data import build_seed_listing


class UserPayload(BaseModel):
    key: str
    name: str
    phone: str


class EvaluateListingsRequest(BaseModel):
    source_seeds: dict[str, list[str]] = Field(default_factory=dict)
    users: list[UserPayload] = Field(default_factory=list)
    sheet_id: str | None = None
    sheet_tab: str | None = None


class HandleReplyRequest(BaseModel):
    from_number: str
    body: str
    raw_body: str | None = None
    listing_id: str | None = None
    twilio_message_sid: str | None = None


def _build_alert_payload(listing, score: float, users: list[UserPayload]) -> dict[str, Any]:
    body = (
        f"[ID:{listing.listing_id}] "
        f"{score}/100 {listing.address} "
        f"{int(listing.beds or 0)}BR ${listing.rent}.\n"
        f"{listing.listing_url}\n"
        "Reply 1 schedule, 2 save, 3 pass, 4 more"
    )
    return {
        "listing_id": listing.listing_id,
        "body": body,
        "users": [{"key": user.key, "phone": user.phone} for user in users],
    }


def create_app() -> FastAPI:
    settings = Settings.from_env()
    store = JsonStateStore(settings.state_store_dir)
    outreach_service = OutreachService()
    app = FastAPI(title="Apartment Search Bot API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/evaluate-listings")
    def evaluate_listings(payload: EvaluateListingsRequest) -> dict[str, Any]:
        dashboard_rows: list[dict[str, str]] = []
        sms_alerts: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        queue_state = store.get_queue()

        for source_name, urls in payload.source_seeds.items():
            try:
                if source_name == "craigslist":
                    listings = CraigslistAdapter(source_urls=urls).fetch_listings()
                else:
                    listings = [build_seed_listing(source_name, url) for url in urls]
            except Exception as exc:
                skipped.extend(
                    {
                        "listing_id": "",
                        "source": source_name,
                        "listing_url": url,
                        "geo_reason": "",
                        "filter_reasons": [f"source fetch failed: {type(exc).__name__}: {exc}"],
                    }
                    for url in urls
                )
                continue

            for listing in listings:
                store.save_listing(listing)
                listing_state = store.get_state(listing.listing_id)
                store.save_state(listing_state)
                evaluation = evaluate_listing(listing, settings)

                if evaluation.score_result is None or evaluation.decision_result is None:
                    skipped.append(
                        {
                            "listing_id": listing.listing_id,
                            "source": source_name,
                            "listing_url": listing.listing_url,
                            "geo_reason": evaluation.geo_result.reason,
                            "filter_reasons": evaluation.filter_reasons,
                        }
                    )
                    continue

                if evaluation.decision_result.write_dashboard:
                    row = build_dashboard_row(listing, evaluation.score_result, listing_state)
                    dashboard_rows.append(asdict(row))

                if evaluation.decision_result.send_sms:
                    listing.raw_payload["queue_score"] = evaluation.score_result.score
                    store.save_listing(listing)
                    queue_state = store.enqueue_listing(listing.listing_id, evaluation.score_result.score)

        active_listing_id = queue_state.active_listing_id
        activated_new_listing = False
        if active_listing_id is None:
            active_listing_id = store.activate_next_listing()
            activated_new_listing = active_listing_id is not None

        if active_listing_id and activated_new_listing:
            active_listing = store.get_listing(active_listing_id)
            if active_listing:
                active_state = store.get_state(active_listing_id)
                active_score = score_listing(active_listing, settings).score
                if derive_overall_status(active_state) in {OverallListingStatus.NEW, OverallListingStatus.SAVED_BY_ONE}:
                    sms_alerts.append(_build_alert_payload(active_listing, active_score, payload.users))
                    for user in payload.users:
                        store.record_alert(user.phone, active_listing_id)

        return {
            "dashboard_rows": dashboard_rows,
            "sms_alerts": sms_alerts,
            "skipped": skipped,
        }

    @app.post("/handle-reply")
    def handle_reply(payload: HandleReplyRequest) -> dict[str, Any]:
        from_number = normalize_phone(payload.from_number)
        user_map = {normalize_phone(user.phone): user for user in settings.users if normalize_phone(user.phone)}
        user = user_map.get(from_number)
        if user is None:
            return {"ok": False, "reply_text": "Unknown sender number."}

        parsed = parse_sms_command(payload.body)
        if not parsed.valid:
            return {"ok": False, "reply_text": parsed.error_message}

        queue_state = store.get_queue()
        listing_id = queue_state.active_listing_id or payload.listing_id or store.lookup_recent_listing_for_phone(payload.from_number)
        if not listing_id:
            return {"ok": False, "reply_text": "Could not match this reply to a listing."}

        listing = store.get_listing(listing_id)
        if listing is None:
            return {"ok": False, "reply_text": "Listing not found in local state."}

        listing_state = store.get_state(listing_id)
        result = handle_user_reply(
            listing=listing,
            listing_state=listing_state,
            user_key=user.key,
            normalized_command=parsed.normalized_command,
            action=parsed.action,
            outreach_service=outreach_service,
            settings=settings,
        )
        store.save_state(listing_state)

        reply_text = str(result.get("message", "Reply processed."))
        response: dict[str, Any] = {
            "ok": bool(result.get("success", True)),
            "reply_text": reply_text,
            "listing_id": listing_id,
            "status": derive_overall_status(listing_state).value,
            "notify_other_user": False,
        }

        response["dashboard_row"] = asdict(build_dashboard_row(listing, score_listing(listing, settings), listing_state))

        if bool(result.get("is_terminal", False)):
            store.mark_queue_completed(listing_id)
            next_listing_id = store.activate_next_listing()
            if next_listing_id:
                next_listing = store.get_listing(next_listing_id)
                if next_listing is not None:
                    next_score = score_listing(next_listing, settings).score
                    next_alert = _build_alert_payload(next_listing, next_score, list(settings.users))
                    response["next_sms_alert"] = next_alert
                    for user_config in settings.users:
                        store.record_alert(user_config.phone, next_listing_id)

        if parsed.action and parsed.action.value == "schedule":
            other_users = [candidate for candidate in settings.users if candidate.key != user.key]
            if other_users:
                response["notify_other_user"] = True
                response["notification_targets"] = [candidate.phone for candidate in other_users]
                response["notification_message"] = (
                    f"{user.name} requested outreach for {listing.address}. "
                    "Duplicate scheduling is now blocked."
                )

        return response

    return app


app = create_app()
