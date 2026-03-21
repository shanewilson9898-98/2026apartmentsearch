from __future__ import annotations

import re

from apartment_bot.core.models import ParsedSmsCommand, UserActionType


COMMAND_MAP = {
    "1": UserActionType.SCHEDULE,
    "schedule": UserActionType.SCHEDULE,
    "2": UserActionType.SAVE,
    "save": UserActionType.SAVE,
    "3": UserActionType.PASS,
    "pass": UserActionType.PASS,
    "4": UserActionType.NONE,
    "more": UserActionType.NONE,
}


def parse_sms_command(body: str) -> ParsedSmsCommand:
    normalized = body.strip().lower()
    compact = re.sub(r"\s+", " ", normalized).strip()
    canonical = re.sub(r"[^a-z0-9/ ]+", "", compact)
    variants = [
        normalized,
        compact,
        canonical,
        canonical.replace(" / ", "/").replace("/ ", "/").replace(" /", "/"),
    ]

    action = None
    matched_variant = normalized
    for variant in variants:
        if variant in COMMAND_MAP:
            action = COMMAND_MAP[variant]
            matched_variant = variant
            break

    if action is None:
        token = canonical.split(" ", 1)[0]
        token = token.split("/", 1)[0]
        action = COMMAND_MAP.get(token)
        matched_variant = token

    if action is None:
        return ParsedSmsCommand(
            valid=False,
            action=None,
            normalized_command=canonical,
            error_message="Reply with 1/schedule, 2/save, 3/pass, or 4/more.",
        )
    return ParsedSmsCommand(valid=True, action=action, normalized_command=matched_variant)


def is_more_command(parsed: ParsedSmsCommand) -> bool:
    return parsed.normalized_command in {"4", "more"}
