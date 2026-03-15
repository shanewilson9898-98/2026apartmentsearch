from __future__ import annotations

from apartment_bot.adapters.base import ListingSourceAdapter
from apartment_bot.core.models import Listing


class CraigslistAdapter(ListingSourceAdapter):
    source_name = "craigslist"

    def fetch_listings(self) -> list[Listing]:
        # TODO: Implement Craigslist fetch/parsing path.
        # TODO: Add parser selectors and contact extraction rules.
        return []
