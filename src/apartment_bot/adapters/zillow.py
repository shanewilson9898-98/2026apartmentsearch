from __future__ import annotations

from apartment_bot.adapters.base import ListingSourceAdapter
from apartment_bot.core.models import Listing


class ZillowAdapter(ListingSourceAdapter):
    source_name = "zillow"

    def fetch_listings(self) -> list[Listing]:
        # TODO: Implement Zillow fetch/parsing path.
        # TODO: Add parser selectors or API request details once the collection method is chosen.
        return []
