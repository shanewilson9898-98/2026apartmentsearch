from __future__ import annotations

import json
from hashlib import sha1
from functools import lru_cache
from dataclasses import asdict
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import FastAPI
from pydantic import BaseModel, Field

from apartment_bot.adapters.apartments_com import ApartmentsComAdapter
from apartment_bot.adapters.craigslist import CraigslistAdapter
from apartment_bot.adapters.zillow import ZillowAdapter
from apartment_bot.config import Settings
from apartment_bot.core.models import Listing, ListingSource, OverallListingStatus
from apartment_bot.core.normalize import infer_bool_from_text, infer_completeness_score, normalize_phone
from apartment_bot.core.presentation import build_dashboard_row
from apartment_bot.core.scoring import score_listing
from apartment_bot.core.sms import parse_sms_command
from apartment_bot.core.state import derive_overall_status, is_terminal_status
from apartment_bot.core.store import JsonStateStore
from apartment_bot.integrations.outreach import OutreachService
from apartment_bot.orchestration.handlers import handle_user_reply
from apartment_bot.orchestration.pipeline import evaluate_listing


class UserPayload(BaseModel):
    key: str
    name: str
    phone: str


class EvaluateListingsRequest(BaseModel):
    source_seeds: dict[str, list[Any]] = Field(default_factory=dict)
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
        discovery_summary: dict[str, dict[str, int]] = {}
        queue_state = store.get_queue()

        for source_name, urls in payload.source_seeds.items():
            source_summary = {"discovered": 0, "new": 0, "already_seen": 0}
            try:
                listings = _load_seed_listings(source_name, urls)
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
                discovery_summary[source_name] = source_summary
                continue

            for listing in listings:
                source_summary["discovered"] += 1
                if store.has_seen_listing(listing.listing_id):
                    source_summary["already_seen"] += 1
                    continue

                source_summary["new"] += 1
                store.save_listing(listing)
                listing_state = store.get_state(listing.listing_id)
                store.save_state(listing_state)
                evaluation = evaluate_listing(listing, settings)
                store.mark_listing_seen(listing)

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

            discovery_summary[source_name] = source_summary

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
            "discovery_summary": discovery_summary,
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


def _load_seed_listings(source_name: str, seeds: list[Any]) -> list[Listing]:
    direct_listings = [_build_listing_from_seed(source_name, seed) for seed in seeds if isinstance(seed, dict)]
    source_urls = [str(seed).strip() for seed in seeds if isinstance(seed, str) and str(seed).strip()]
    if not source_urls:
        return direct_listings
    adapter = _build_source_adapter(source_name, source_urls)
    return [*direct_listings, *adapter.fetch_listings()]


def _build_source_adapter(source_name: str, urls: list[str]):
    if source_name == "craigslist":
        return CraigslistAdapter(source_urls=urls)
    if source_name == "zillow":
        return ZillowAdapter(source_urls=urls)
    if source_name == "apartments_com":
        return ApartmentsComAdapter(source_urls=urls)
    raise ValueError(f"Unsupported source: {source_name}")


def _build_listing_from_seed(source_name: str, seed: dict[str, Any]) -> Listing:
    listing_url = str(seed.get("listing_url") or "").strip()
    if not listing_url:
        raise ValueError(f"Missing listing_url for {source_name} seed")

    source = _listing_source_for_name(source_name)
    address = _nullable_string(seed.get("address"))
    description = _nullable_string(seed.get("description")) or ""
    feature_values = seed.get("features") if isinstance(seed.get("features"), list) else []
    features = [str(value).strip() for value in feature_values if str(value).strip()]
    text_signals = [
        address or "",
        description,
        _nullable_string(seed.get("building_name")) or "",
        _nullable_string(seed.get("availability_text")) or "",
        *features,
    ]
    coordinates = _coordinates_for_seed(seed, address)

    return Listing.now(
        listing_id=_seed_listing_id(source_name, listing_url),
        source=source,
        source_listing_id=_nullable_string(seed.get("source_listing_id")) or listing_url,
        address=address,
        rent=_int_or_none(seed.get("rent")),
        beds=_float_or_none(seed.get("beds")),
        baths=_float_or_none(seed.get("baths")),
        sqft=_int_or_none(seed.get("sqft")),
        description=description,
        features=features,
        listing_url=listing_url,
        images=[str(value).strip() for value in seed.get("images", []) if str(value).strip()] if isinstance(seed.get("images"), list) else [],
        lat=coordinates[0],
        lng=coordinates[1],
        has_dishwasher=_bool_or_infer(seed.get("has_dishwasher"), text_signals, [r"\bdishwasher\b"]),
        has_in_unit_laundry=_bool_or_infer(
            seed.get("has_in_unit_laundry"),
            text_signals,
            [r"\bin[-\s]?unit laundry\b", r"\bwasher/dryer in unit\b", r"\bw/d in unit\b"],
        ),
        has_parking=_bool_or_infer(seed.get("has_parking"), text_signals, [r"\bparking\b", r"\bgarage\b"]),
        pet_friendly=_bool_or_infer(seed.get("pet_friendly"), text_signals, [r"\bpet friendly\b", r"\bdogs? ok\b", r"\bcats? ok\b"]),
        has_private_outdoor_space=_bool_or_infer(
            seed.get("has_private_outdoor_space"),
            text_signals,
            [r"\bbalcony\b", r"\bpatio\b", r"\bdeck\b", r"\bterrace\b"],
        ),
        has_fitness_center=_bool_or_infer(seed.get("has_fitness_center"), text_signals, [r"\bfitness center\b", r"\bgym\b"]),
        natural_light_signal=_bool_or_infer(seed.get("natural_light_signal"), text_signals, [r"\bnatural light\b", r"\bsunny\b"]),
        renovated_kitchen_signal=_bool_or_infer(
            seed.get("renovated_kitchen_signal"),
            text_signals,
            [r"\brenovated kitchen\b", r"\bupdated kitchen\b", r"\bnewer appliances\b"],
        ),
        quiet_street_signal=_bool_or_infer(seed.get("quiet_street_signal"), text_signals, [r"\bquiet\b", r"\bresidential street\b"]),
        caltrain_signal=_bool_or_infer(seed.get("caltrain_signal"), text_signals, [r"\bcaltrain\b"]),
        walkability_signal=_bool_or_infer(seed.get("walkability_signal"), text_signals, [r"\bwalkable\b", r"\bwalk to\b"]),
        street_parking_only=_bool_or_infer(seed.get("street_parking_only"), text_signals, [r"\bstreet parking\b"]),
        older_interiors_signal=bool(seed.get("older_interiors_signal", False)),
        ground_floor_signal=bool(seed.get("ground_floor_signal", False)),
        unclear_availability_signal=bool(seed.get("unclear_availability_signal", False)),
        broker_fee_signal=bool(seed.get("broker_fee_signal", False)),
        completeness_score=infer_completeness_score(
            address,
            _int_or_none(seed.get("rent")),
            description,
            [str(value).strip() for value in seed.get("images", []) if str(value).strip()] if isinstance(seed.get("images"), list) else [],
        ),
        scam_signal=bool(seed.get("scam_signal", False)),
        income_restricted_signal=bool(seed.get("income_restricted_signal", False)),
        senior_housing_signal=bool(seed.get("senior_housing_signal", False)),
        student_housing_signal=bool(seed.get("student_housing_signal", False)),
        building_name=_nullable_string(seed.get("building_name")),
        availability_text=_nullable_string(seed.get("availability_text")),
        contact_name=_nullable_string(seed.get("contact_name")),
        contact_phone=_nullable_string(seed.get("contact_phone")),
        contact_email=_nullable_string(seed.get("contact_email")),
        raw_payload={"seed_mode": True, "source_seed": seed},
    )


def _listing_source_for_name(source_name: str) -> ListingSource:
    if source_name == "craigslist":
        return ListingSource.CRAIGSLIST
    if source_name == "zillow":
        return ListingSource.ZILLOW
    if source_name == "apartments_com":
        return ListingSource.APARTMENTS_DOT_COM
    raise ValueError(f"Unsupported source: {source_name}")


def _seed_listing_id(source_name: str, listing_url: str) -> str:
    return f"{source_name}_{sha1(listing_url.encode('utf-8')).hexdigest()[:12]}"


def _coordinates_for_seed(seed: dict[str, Any], address: str | None) -> tuple[float | None, float | None]:
    lat = _float_or_none(seed.get("lat"))
    lng = _float_or_none(seed.get("lng"))
    if lat is not None and lng is not None:
        return lat, lng
    if not address:
        return None, None
    return _geocode_address(address)


def _nullable_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip().replace(",", "")
    try:
        return int(float(text))
    except ValueError:
        return None


def _float_or_none(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def _bool_or_infer(value: Any, texts: list[str], patterns: list[str]) -> bool:
    if isinstance(value, bool):
        return value
    return infer_bool_from_text(texts, patterns)


@lru_cache(maxsize=256)
def _geocode_address(address: str) -> tuple[float | None, float | None]:
    params = urlencode(
        {
            "address": address,
            "benchmark": "Public_AR_Current",
            "format": "json",
        }
    )
    request = Request(
        f"https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?{params}",
        headers={"User-Agent": "apartment-search-bot/1.0"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None, None

    matches = payload.get("result", {}).get("addressMatches", [])
    if not matches:
        return None, None

    coordinates = matches[0].get("coordinates", {})
    x = coordinates.get("x")
    y = coordinates.get("y")
    if x is None or y is None:
        return None, None
    return float(y), float(x)


app = create_app()
