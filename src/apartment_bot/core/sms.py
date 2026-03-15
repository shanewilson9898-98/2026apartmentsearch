from __future__ import annotations

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
    action = COMMAND_MAP.get(normalized)
    if action is None:
        return ParsedSmsCommand(
            valid=False,
            action=None,
            normalized_command=normalized,
            error_message="Reply with 1/schedule, 2/save, 3/pass, or 4/more.",
        )
    return ParsedSmsCommand(valid=True, action=action, normalized_command=normalized)


def is_more_command(parsed: ParsedSmsCommand) -> bool:
    return parsed.normalized_command in {"4", "more"}
