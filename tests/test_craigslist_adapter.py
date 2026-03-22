from __future__ import annotations

import unittest

from apartment_bot.adapters.craigslist import CraigslistAdapter


SEARCH_HTML = """
<html>
  <body>
    <a class="cl-app-anchor" href="/sfc/apa/d/san-francisco-first-place/1111111111.html">First</a>
    <a class="cl-app-anchor" href="https://sfbay.craigslist.org/sfc/apa/d/san-francisco-second-place/2222222222.html">Second</a>
    <a class="cl-app-anchor" href="/sfc/apa/d/san-francisco-first-place/1111111111.html">Duplicate</a>
  </body>
</html>
"""


LISTING_HTML = """
<html>
  <head>
    <script type="application/ld+json" id="ld_posting_data">
      {
        "name": "Nice Apartment",
        "numberOfBedrooms": 2,
        "numberOfBathroomsTotal": 2,
        "latitude": 37.7701,
        "longitude": -122.3901
      }
    </script>
  </head>
  <body>
    <span id="titletextonly">Nice Apartment</span>
    <span class="price">$5250</span>
    <span class="housing">2BR / 2Ba / 950ft2</span>
    <h2 class="street-address">Mission Bay, San Francisco, CA</h2>
    <section id="postingbody">In-unit laundry, dishwasher, parking.</section>
  </body>
</html>
"""


class CraigslistAdapterTests(unittest.TestCase):
    def test_extract_listing_urls_from_search_results(self) -> None:
        adapter = CraigslistAdapter()

        urls = adapter.extract_listing_urls("https://sfbay.craigslist.org/search/sfc/apa", SEARCH_HTML)

        self.assertEqual(
            urls,
            [
                "https://sfbay.craigslist.org/sfc/apa/d/san-francisco-first-place/1111111111.html",
                "https://sfbay.craigslist.org/sfc/apa/d/san-francisco-second-place/2222222222.html",
            ],
        )

    def test_fetch_listings_expands_search_page_and_dedupes_results(self) -> None:
        class FakeCraigslistAdapter(CraigslistAdapter):
            def _fetch_html(self, url: str) -> str:
                if "search" in url:
                    return SEARCH_HTML
                return LISTING_HTML

        adapter = FakeCraigslistAdapter(
            source_urls=["https://sfbay.craigslist.org/search/sfc/apa"],
        )

        listings = adapter.fetch_listings()

        self.assertEqual(len(listings), 2)
        self.assertEqual(
            [listing.listing_id for listing in listings],
            ["craigslist_1111111111", "craigslist_2222222222"],
        )


if __name__ == "__main__":
    unittest.main()
