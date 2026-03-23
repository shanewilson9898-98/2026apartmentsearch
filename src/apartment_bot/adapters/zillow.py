from __future__ import annotations

from apartment_bot.adapters.base import ListingSourceAdapter
from apartment_bot.core.models import Listing


class ZillowAdapter(ListingSourceAdapter):
    source_name = "zillow"

    def __init__(self, source_urls: list[str] | None = None, timeout_seconds: int = 20) -> None:
        self.source_urls = source_urls or []
        self.timeout_seconds = timeout_seconds

    def fetch_listings(self) -> list[Listing]:
        # TODO: Implement Zillow fetch/parsing path.
        # TODO: Add parser selectors or API request details once the collection method is chosen.
        return []
