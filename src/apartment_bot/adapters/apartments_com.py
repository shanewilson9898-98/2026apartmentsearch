from __future__ import annotations

from apartment_bot.adapters.base import ListingSourceAdapter
from apartment_bot.core.models import Listing


class ApartmentsComAdapter(ListingSourceAdapter):
    source_name = "apartments_com"

    def __init__(self, source_urls: list[str] | None = None, timeout_seconds: int = 20) -> None:
        self.source_urls = source_urls or []
        self.timeout_seconds = timeout_seconds

    def fetch_listings(self) -> list[Listing]:
        # TODO: Implement Apartments.com fetch/parsing path.
        # TODO: Add parser selectors and contact extraction rules.
        return []
