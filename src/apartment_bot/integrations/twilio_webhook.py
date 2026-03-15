from __future__ import annotations

from dataclasses import dataclass

from apartment_bot.core.models import ParsedSmsCommand
from apartment_bot.core.sms import parse_sms_command


@dataclass(frozen=True)
class TwilioWebhookPayload:
    from_number: str
    body: str
    listing_id: str


def parse_webhook_payload(payload: dict[str, str]) -> TwilioWebhookPayload:
    # TODO: Validate the Twilio signature using the webhook secret once the production webhook URL is known.
    # TODO: Confirm how listing_id will be embedded for replies: short code, message prefix, or state lookup by message SID.
    return TwilioWebhookPayload(
        from_number=payload.get("From", ""),
        body=payload.get("Body", ""),
        listing_id=payload.get("listing_id", ""),
    )


def parse_twilio_command(payload: dict[str, str]) -> tuple[TwilioWebhookPayload, ParsedSmsCommand]:
    webhook = parse_webhook_payload(payload)
    return webhook, parse_sms_command(webhook.body)
