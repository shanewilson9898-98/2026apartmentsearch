from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from apartment_bot.core.models import Listing, ListingSource, ListingState, OutreachStatus, QueueState, UserAction, UserActionType
from apartment_bot.core.normalize import normalize_phone


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _deserialize_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def listing_to_dict(listing: Listing) -> dict:
    payload = asdict(listing)
    payload["source"] = listing.source.value
    payload["timestamp"] = listing.timestamp.isoformat()
    return payload


def listing_from_dict(payload: dict) -> Listing:
    return Listing(
        **{
            **payload,
            "source": ListingSource(payload["source"]),
            "timestamp": datetime.fromisoformat(payload["timestamp"]),
        }
    )


def state_to_dict(state: ListingState) -> dict:
    return {
        "listing_id": state.listing_id,
        "user_actions": {
            user_key: {
                "user_key": action.user_key,
                "action": action.action.value,
                "timestamp": _serialize_datetime(action.timestamp),
            }
            for user_key, action in state.user_actions.items()
        },
        "outreach_status": state.outreach_status.value,
        "outreach_triggered_by": state.outreach_triggered_by,
        "outreach_timestamp": _serialize_datetime(state.outreach_timestamp),
        "manual_follow_up_required": state.manual_follow_up_required,
    }


def state_from_dict(payload: dict) -> ListingState:
    return ListingState(
        listing_id=payload["listing_id"],
        user_actions={
            user_key: UserAction(
                user_key=action_payload["user_key"],
                action=UserActionType(action_payload["action"]),
                timestamp=_deserialize_datetime(action_payload["timestamp"]) or datetime.utcnow(),
            )
            for user_key, action_payload in payload.get("user_actions", {}).items()
        },
        outreach_status=OutreachStatus(payload.get("outreach_status", OutreachStatus.NOT_STARTED.value)),
        outreach_triggered_by=payload.get("outreach_triggered_by"),
        outreach_timestamp=_deserialize_datetime(payload.get("outreach_timestamp")),
        manual_follow_up_required=payload.get("manual_follow_up_required", False),
    )


class JsonStateStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._listings_path = self.base_dir / "listings.json"
        self._states_path = self.base_dir / "states.json"
        self._alerts_path = self.base_dir / "alerts.json"
        self._queue_path = self.base_dir / "queue.json"

    def _read_json(self, path: Path) -> dict:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def save_listing(self, listing: Listing) -> None:
        payload = self._read_json(self._listings_path)
        payload[listing.listing_id] = listing_to_dict(listing)
        self._write_json(self._listings_path, payload)

    def get_listing(self, listing_id: str) -> Listing | None:
        payload = self._read_json(self._listings_path)
        item = payload.get(listing_id)
        return listing_from_dict(item) if item else None

    def save_state(self, state: ListingState) -> None:
        payload = self._read_json(self._states_path)
        payload[state.listing_id] = state_to_dict(state)
        self._write_json(self._states_path, payload)

    def get_state(self, listing_id: str) -> ListingState:
        payload = self._read_json(self._states_path)
        item = payload.get(listing_id)
        if item:
            return state_from_dict(item)
        return ListingState(listing_id=listing_id)

    def record_alert(self, phone_number: str, listing_id: str) -> None:
        payload = self._read_json(self._alerts_path)
        normalized_phone = normalize_phone(phone_number)
        payload[normalized_phone] = {
            "listing_id": listing_id,
            "updated_at": datetime.utcnow().isoformat(),
        }
        self._write_json(self._alerts_path, payload)

    def lookup_recent_listing_for_phone(self, phone_number: str) -> str | None:
        payload = self._read_json(self._alerts_path)
        normalized_phone = normalize_phone(phone_number)
        record = payload.get(normalized_phone, {})
        return record.get("listing_id")

    def get_queue(self) -> QueueState:
        payload = self._read_json(self._queue_path)
        if not payload:
            return QueueState()
        return QueueState(
            active_listing_id=payload.get("active_listing_id"),
            pending_listing_ids=payload.get("pending_listing_ids", []),
            completed_listing_ids=payload.get("completed_listing_ids", []),
        )

    def save_queue(self, queue_state: QueueState) -> None:
        self._write_json(
            self._queue_path,
            {
                "active_listing_id": queue_state.active_listing_id,
                "pending_listing_ids": queue_state.pending_listing_ids,
                "completed_listing_ids": queue_state.completed_listing_ids,
            },
        )

    def enqueue_listing(self, listing_id: str, score: float) -> QueueState:
        queue_state = self.get_queue()
        if listing_id == queue_state.active_listing_id:
            return queue_state
        if listing_id in queue_state.completed_listing_ids or listing_id in queue_state.pending_listing_ids:
            return queue_state
        queue_state.pending_listing_ids.append(listing_id)
        scores = {
            queued_id: score if queued_id == listing_id else (self.get_listing(queued_id).raw_payload.get("queue_score", 0) if self.get_listing(queued_id) else 0)
            for queued_id in queue_state.pending_listing_ids
        }
        queue_state.pending_listing_ids.sort(key=lambda queued_id: scores.get(queued_id, 0), reverse=True)
        self.save_queue(queue_state)
        return queue_state

    def mark_queue_completed(self, listing_id: str) -> QueueState:
        queue_state = self.get_queue()
        if listing_id not in queue_state.completed_listing_ids:
            queue_state.completed_listing_ids.append(listing_id)
        queue_state.pending_listing_ids = [queued_id for queued_id in queue_state.pending_listing_ids if queued_id != listing_id]
        if queue_state.active_listing_id == listing_id:
            queue_state.active_listing_id = None
        self.save_queue(queue_state)
        return queue_state

    def activate_next_listing(self) -> str | None:
        queue_state = self.get_queue()
        if queue_state.active_listing_id:
            return queue_state.active_listing_id
        if not queue_state.pending_listing_ids:
            return None
        queue_state.active_listing_id = queue_state.pending_listing_ids.pop(0)
        self.save_queue(queue_state)
        return queue_state.active_listing_id
