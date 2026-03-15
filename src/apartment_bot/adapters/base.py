from __future__ import annotations

from abc import ABC, abstractmethod

from apartment_bot.core.models import Listing


class ListingSourceAdapter(ABC):
    source_name: str

    @abstractmethod
    def fetch_listings(self) -> list[Listing]:
        raise NotImplementedError
