from __future__ import annotations

from dataclasses import dataclass

from apartment_bot.config import Settings


@dataclass(frozen=True)
class OutboundSms:
    to_number: str
    body: str


class TwilioSmsClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send_messages(self, messages: list[OutboundSms]) -> list[OutboundSms]:
        # TODO: Use TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER.
        # TODO: Add delivery error handling and idempotency once the webhook URL and delivery path are fixed.
        return messages
