from __future__ import annotations

from apartment_bot.config import Settings
from apartment_bot.core.models import DecisionBand, DecisionResult


def decide_score_band(score: float, settings: Settings) -> DecisionResult:
    if score >= settings.high_score_threshold:
        return DecisionResult(DecisionBand.HIGH, send_sms=True, write_dashboard=True, ignore=False)
    if score >= settings.medium_score_threshold:
        return DecisionResult(DecisionBand.MEDIUM, send_sms=False, write_dashboard=True, ignore=False)
    return DecisionResult(DecisionBand.LOW, send_sms=False, write_dashboard=False, ignore=True)
