from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ListingSource(str, Enum):
    ZILLOW = "zillow"
    CRAIGSLIST = "craigslist"
    APARTMENTS_DOT_COM = "apartments_com"


class GeoMode(str, Enum):
    SAN_FRANCISCO = "san_francisco"
    PENINSULA = "peninsula"


class DecisionBand(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class UserActionType(str, Enum):
    NONE = "none"
    SAVE = "save"
    PASS = "pass"
    SCHEDULE = "schedule"


class OverallListingStatus(str, Enum):
    NEW = "new"
    SAVED = "saved"
    PASSED = "passed"
    SCHEDULED = "scheduled"
    MANUAL_FOLLOW_UP = "manual_follow_up"


class OutreachStatus(str, Enum):
    NOT_STARTED = "not_started"
    SENT = "sent"
    BLOCKED_DUPLICATE = "blocked_duplicate"
    NEEDS_MANUAL_FOLLOW_UP = "needs_manual_follow_up"


@dataclass(frozen=True)
class Point:
    name: str
    lat: float
    lng: float


@dataclass(frozen=True)
class Polygon:
    name: str
    coordinates: list[tuple[float, float]]


@dataclass(frozen=True)
class GeoDataset:
    sf_polygons: list[Polygon]
    sf_gyms: list[Point]
    peninsula_gyms: list[Point]


@dataclass
class Listing:
    listing_id: str
    source: ListingSource
    source_listing_id: str
    address: str | None
    rent: int | None
    beds: float | None
    baths: float | None
    sqft: int | None
    description: str
    features: list[str]
    listing_url: str
    images: list[str]
    timestamp: datetime
    lat: float | None
    lng: float | None
    has_dishwasher: bool = False
    has_in_unit_laundry: bool = False
    has_parking: bool = False
    pet_friendly: bool = False
    has_private_outdoor_space: bool = False
    has_fitness_center: bool = False
    natural_light_signal: bool = False
    renovated_kitchen_signal: bool = False
    quiet_street_signal: bool = False
    caltrain_signal: bool = False
    walkability_signal: bool = False
    street_parking_only: bool = False
    older_interiors_signal: bool = False
    ground_floor_signal: bool = False
    unclear_availability_signal: bool = False
    broker_fee_signal: bool = False
    completeness_score: float = 1.0
    scam_signal: bool = False
    income_restricted_signal: bool = False
    senior_housing_signal: bool = False
    student_housing_signal: bool = False
    building_name: str | None = None
    availability_text: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def now(cls, **kwargs: Any) -> "Listing":
        return cls(timestamp=datetime.now(timezone.utc), **kwargs)


@dataclass(frozen=True)
class GeoQualificationResult:
    qualifies: bool
    mode: GeoMode | None
    reason: str
    distance_to_supporting_gym_miles: float | None = None
    supporting_gym_name: str | None = None


@dataclass(frozen=True)
class FilterResult:
    passed: bool
    reasons: list[str]


@dataclass(frozen=True)
class ScoreResult:
    score: float
    pros: list[str]
    cons: list[str]


@dataclass(frozen=True)
class DecisionResult:
    band: DecisionBand
    send_sms: bool
    write_dashboard: bool
    ignore: bool


@dataclass(frozen=True)
class ParsedSmsCommand:
    valid: bool
    action: UserActionType | None
    normalized_command: str
    error_message: str | None = None


@dataclass
class UserAction:
    user_key: str
    action: UserActionType
    timestamp: datetime


@dataclass
class ListingState:
    listing_id: str
    user_actions: dict[str, UserAction] = field(default_factory=dict)
    outreach_status: OutreachStatus = OutreachStatus.NOT_STARTED
    outreach_triggered_by: str | None = None
    outreach_timestamp: datetime | None = None
    manual_follow_up_required: bool = False


@dataclass(frozen=True)
class StateUpdateResult:
    listing_state: ListingState
    overall_status: OverallListingStatus
    duplicate_schedule_blocked: bool
    notify_other_user: bool
    notification_message: str | None


@dataclass(frozen=True)
class DashboardRow:
    listing_id: str
    status: str
    address: str
    rent: str
    beds_baths: str
    score: str
    source: str
    listing_url: str
    shane_action: str
    wife_action: str
