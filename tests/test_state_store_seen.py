from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from apartment_bot.core.models import ListingSource
from apartment_bot.core.store import JsonStateStore
from apartment_bot.orchestration.sample_data import build_seed_listing


class JsonStateStoreSeenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="apartment-bot-store-"))
        self.store = JsonStateStore(self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_marks_listing_seen_by_listing_id(self) -> None:
        listing = build_seed_listing("zillow", "https://example.com/listing-one")

        self.assertFalse(self.store.has_seen_listing(listing.listing_id))
        self.store.mark_listing_seen(listing)
        self.assertTrue(self.store.has_seen_listing(listing.listing_id))


if __name__ == "__main__":
    unittest.main()
