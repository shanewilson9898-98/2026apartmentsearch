from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(dotenv_path: Path = Path(".env")) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value is not None else default


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value is not None else default


@dataclass(frozen=True)
class UserConfig:
    key: str
    name: str
    phone: str


@dataclass(frozen=True)
class Settings:
    env: str
    geo_data_dir: Path
    state_store_dir: Path
    target_rent: int
    hard_max_rent: int
    min_beds: int
    min_baths: int
    preferred_min_sqft: int
    sf_gym_threshold_miles: float
    peninsula_gym_threshold_miles: float
    high_score_threshold: float
    medium_score_threshold: float
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str
    users: tuple[UserConfig, UserConfig]
    google_sheets_spreadsheet_id: str
    google_service_account_json: str
    google_sheet_tab: str
    n8n_shared_secret: str
    outreach_sender_name: str
    require_on_site_fitness_fallback: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv()
        geo_dir = Path(os.getenv("GEO_DATA_DIR", "./data/geo")).expanduser()
        return cls(
            env=os.getenv("APARTMENT_BOT_ENV", "dev"),
            geo_data_dir=geo_dir,
            state_store_dir=Path(os.getenv("STATE_STORE_DIR", "./data/runtime")).expanduser(),
            target_rent=_get_int("TARGET_RENT", 4500),
            hard_max_rent=_get_int("HARD_MAX_RENT", 5750),
            min_beds=_get_int("MIN_BEDS", 2),
            min_baths=_get_int("MIN_BATHS", 1),
            preferred_min_sqft=_get_int("PREFERRED_MIN_SQFT", 850),
            sf_gym_threshold_miles=_get_float("SF_GYM_THRESHOLD_MILES", 0.5),
            peninsula_gym_threshold_miles=_get_float("PENINSULA_GYM_THRESHOLD_MILES", 2.0),
            high_score_threshold=_get_float("HIGH_SCORE_THRESHOLD", 75.0),
            medium_score_threshold=_get_float("MEDIUM_SCORE_THRESHOLD", 50.0),
            twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID", "TODO"),
            twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN", "TODO"),
            twilio_from_number=os.getenv("TWILIO_FROM_NUMBER", "TODO"),
            users=(
                UserConfig(
                    key="shane",
                    name=os.getenv("USER_ONE_NAME", "Shane"),
                    phone=os.getenv("USER_ONE_PHONE", "TODO"),
                ),
                UserConfig(
                    key="wife",
                    name=os.getenv("USER_TWO_NAME", "Wife"),
                    phone=os.getenv("USER_TWO_PHONE", "TODO"),
                ),
            ),
            google_sheets_spreadsheet_id=os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "TODO"),
            google_service_account_json=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "TODO"),
            google_sheet_tab=os.getenv("GOOGLE_SHEET_TAB", "Listings"),
            n8n_shared_secret=os.getenv("N8N_SHARED_SECRET", "TODO"),
            outreach_sender_name=os.getenv("OUTREACH_SENDER_NAME", "TODO"),
            require_on_site_fitness_fallback=_get_bool("REQUIRE_ON_SITE_FITNESS_FALLBACK", False),
        )
