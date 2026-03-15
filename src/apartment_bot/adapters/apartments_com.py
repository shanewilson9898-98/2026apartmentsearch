from __future__ import annotations

from apartment_bot.adapters.base import ListingSourceAdapter
from apartment_bot.core.models import Listing


class ApartmentsComAdapter(ListingSourceAdapter):
    source_name = "apartments_com"

    def fetch_listings(self) -> list[Listing]:
        # TODO: Implement Apartments.com fetch/parsing path.
        # TODO: Add parser selectors and contact extraction rules.
        return []
