from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from apartment_bot.adapters.base import ListingSourceAdapter
from apartment_bot.core.models import Listing, ListingSource
from apartment_bot.core.normalize import infer_bool_from_text, infer_completeness_score


class CraigslistAdapter(ListingSourceAdapter):
    source_name = "craigslist"

    def __init__(self, source_urls: list[str] | None = None, timeout_seconds: int = 20) -> None:
        self.source_urls = source_urls or []
        self.timeout_seconds = timeout_seconds

    def fetch_listings(self) -> list[Listing]:
        listings: list[Listing] = []
        seen_listing_ids: set[str] = set()

        for source_url in self.source_urls:
            for listing_url in self._expand_source_url(source_url):
                html = self._fetch_html(listing_url)
                listing = self.parse_listing_html(listing_url, html)
                if listing.listing_id in seen_listing_ids:
                    continue
                seen_listing_ids.add(listing.listing_id)
                listings.append(listing)

        return listings

    def _expand_source_url(self, source_url: str) -> list[str]:
        html = self._fetch_html(source_url)
        if self._looks_like_listing_url(source_url):
            return [source_url]

        discovered_urls = self.extract_listing_urls(source_url, html)
        if discovered_urls:
            return discovered_urls

        if self._looks_like_listing_page(html):
            return [source_url]

        return []

    def _fetch_html(self, url: str) -> str:
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
                )
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return response.read().decode("utf-8", errors="replace")

    def extract_listing_urls(self, source_url: str, html: str) -> list[str]:
        candidate_urls: list[str] = []
        for tag_match in re.finditer(r"<a\b[^>]*>", html, re.IGNORECASE):
            tag = tag_match.group(0)
            if not any(marker in tag.lower() for marker in ['cl-app-anchor', 'data-id=', 'result-title']):
                continue
            href_match = re.search(r'href="([^"]+/\d+\.html)"', tag, re.IGNORECASE)
            if href_match:
                candidate_urls.append(urljoin(source_url, unescape(href_match.group(1))))

        deduped_urls: list[str] = []
        seen_urls: set[str] = set()
        for url in candidate_urls:
            normalized_url = self._normalize_listing_url(url)
            if normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)
            deduped_urls.append(normalized_url)
        return deduped_urls

    def parse_listing_html(self, url: str, html: str) -> Listing:
        posting_data = self._extract_json_script(html, "ld_posting_data")
        image_data = self._extract_js_json_array(html, "imgList")
        title = self._extract_first(html, r'<span id="titletextonly">(.*?)</span>') or posting_data.get("name") or ""
        price_text = self._extract_first(html, r'<span class="price">\$(.*?)</span>')
        housing_text = self._extract_first(html, r'<span class="housing">(.*?)</span>') or ""
        address = self._extract_first(html, r'<h2 class="street-address">(.*?)</h2>')
        map_address = self._extract_first(html, r'<div class="mapaddress">(.*?)</div>')
        body_html = self._extract_first(html, r'<section id="postingbody">(.*?)</section>')
        description = self._clean_posting_body(body_html or "")
        attr_values = self._extract_attr_values(html)
        features = [feature for feature in attr_values if feature]

        lat, lng = self._extract_lat_lng(html, posting_data)
        beds, baths = self._extract_beds_baths(housing_text, html, posting_data)
        sqft = self._extract_sqft(housing_text)
        listing_id = f"craigslist_{self._extract_posting_id(url, html)}"
        price = int(price_text.replace(",", "")) if price_text else None
        images = [item.get("url", "") for item in image_data if item.get("url")]

        feature_texts = [title, description, address or "", map_address or "", *features]
        has_laundry_in_unit = infer_bool_from_text(
            feature_texts,
            [r"\bin[-\s]?unit laundry\b", r"\bwasher/dryer in unit\b", r"\bw/d in unit\b"],
        )
        has_building_laundry = infer_bool_from_text(
            feature_texts,
            [r"\blaundry in bldg\b", r"\blaundry on site\b", r"\bon[-\s]?site laundry\b"],
        )
        has_dishwasher = infer_bool_from_text(feature_texts, [r"\bdishwasher\b"])
        has_parking = infer_bool_from_text(
            feature_texts,
            [r"\bgarage\b", r"\battached garage\b", r"\boff[-\s]?street parking\b", r"\bparking\b"],
        )
        pet_friendly = infer_bool_from_text(feature_texts, [r"\bcats? ok\b", r"\bdogs? ok\b", r"\bpet friendly\b"])

        return Listing.now(
            listing_id=listing_id,
            source=ListingSource.CRAIGSLIST,
            source_listing_id=self._extract_posting_id(url, html),
            address=address or map_address,
            rent=price,
            beds=beds,
            baths=baths,
            sqft=sqft,
            description=description,
            features=features,
            listing_url=url,
            images=images,
            lat=lat,
            lng=lng,
            has_dishwasher=has_dishwasher,
            has_in_unit_laundry=has_laundry_in_unit,
            has_parking=has_parking,
            pet_friendly=pet_friendly,
            has_private_outdoor_space=infer_bool_from_text(feature_texts, [r"\bbalcony\b", r"\bpatio\b", r"\bdeck\b", r"\bterrace\b"]),
            has_fitness_center=infer_bool_from_text(feature_texts, [r"\bfitness center\b", r"\bgym\b"]),
            natural_light_signal=infer_bool_from_text(feature_texts, [r"\bnatural light", r"\bsunny\b", r"\bbay windows\b"]),
            renovated_kitchen_signal=infer_bool_from_text(
                feature_texts,
                [r"\brenovated kitchen\b", r"\bupdated kitchen\b", r"\bnewer appliances\b", r"\bhigh-end kitchen appliances\b"],
            ),
            quiet_street_signal=infer_bool_from_text(feature_texts, [r"\bquiet\b", r"\bresidential street\b"]),
            caltrain_signal=infer_bool_from_text(feature_texts, [r"\bcaltrain\b"]),
            walkability_signal=infer_bool_from_text(
                feature_texts,
                [r"\bwalk score\b", r"\bwalkable\b", r"\bwalk to\b", r"\bgrocer", r"\brestaurants?\b", r"\bdining\b"],
            ),
            street_parking_only=has_parking is False and infer_bool_from_text(feature_texts, [r"\bstreet parking\b"]),
            older_interiors_signal=infer_bool_from_text(feature_texts, [r"\bdated\b", r"\boriginal\b", r"\bolder interior"]),
            ground_floor_signal=infer_bool_from_text(feature_texts, [r"\bground floor\b", r"\bfirst floor\b"]),
            unclear_availability_signal=infer_bool_from_text(
                feature_texts,
                [r"\bavailable soon\b", r"\bcall for availability\b", r"\bcontact for availability\b", r"\bwaitlist\b"],
            ),
            broker_fee_signal=infer_bool_from_text(feature_texts, [r"\bbroker fee\b", r"\bfee applies\b"]),
            completeness_score=infer_completeness_score(address or map_address, price, description, images),
            scam_signal=infer_bool_from_text(
                feature_texts,
                [r"\bwire money\b", r"\bgift card\b", r"\bwestern union\b", r"\btoo good to be true\b"],
            ),
            income_restricted_signal=infer_bool_from_text(feature_texts, [r"\bincome restricted\b", r"\bbelow market rate\b", r"\bbmr\b"]),
            senior_housing_signal=infer_bool_from_text(feature_texts, [r"\bsenior housing\b", r"\b55\+\b", r"\b62\+\b"]),
            student_housing_signal=infer_bool_from_text(feature_texts, [r"\bstudent housing\b", r"\bstudents only\b"]),
            availability_text=self._extract_availability_text(description),
            raw_payload={
                "source_url": url,
                "ld_posting_data": posting_data,
                "has_building_laundry": has_building_laundry,
            },
        )

    def _extract_first(self, text: str, pattern: str) -> str | None:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if not match:
            return None
        return unescape(self._strip_tags(match.group(1))).strip()

    def _extract_json_script(self, html: str, script_id: str) -> dict:
        match = re.search(
            rf'<script type="application/ld\+json" id="{re.escape(script_id)}"\s*>(.*?)</script>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if not match:
            return {}
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            return {}

    def _extract_js_json_array(self, html: str, variable_name: str) -> list[dict]:
        match = re.search(rf"var {re.escape(variable_name)} = (\[.*?\]);", html, re.DOTALL)
        if not match:
            return []
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return []

    def _extract_attr_values(self, html: str) -> list[str]:
        matches = re.findall(r'<span class="valu">(.*?)</span>', html, re.DOTALL | re.IGNORECASE)
        return [self._strip_tags(match).strip() for match in matches]

    def _extract_posting_id(self, url: str, html: str) -> str:
        match = re.search(r"/(\d+)\.html", url)
        if match:
            return match.group(1)
        match = re.search(r"'pID':\s*(\d+)", html)
        return match.group(1) if match else "unknown"

    def _extract_beds_baths(self, housing_text: str, html: str, posting_data: dict) -> tuple[float | None, float | None]:
        beds = posting_data.get("numberOfBedrooms")
        baths = posting_data.get("numberOfBathroomsTotal")
        if beds is not None or baths is not None:
            return (float(beds) if beds is not None else None, float(baths) if baths is not None else None)
        match = re.search(r"(\d+(?:\.\d+)?)BR\s*/\s*(\d+(?:\.\d+)?)Ba", html, re.IGNORECASE)
        if match:
            return float(match.group(1)), float(match.group(2))
        br_match = re.search(r"(\d+(?:\.\d+)?)br", housing_text, re.IGNORECASE)
        return (float(br_match.group(1)) if br_match else None, None)

    def _extract_sqft(self, housing_text: str) -> int | None:
        match = re.search(r"(\d{3,5})ft2", housing_text.replace(" ", ""), re.IGNORECASE)
        return int(match.group(1)) if match else None

    def _extract_lat_lng(self, html: str, posting_data: dict) -> tuple[float | None, float | None]:
        if posting_data.get("latitude") and posting_data.get("longitude"):
            return float(posting_data["latitude"]), float(posting_data["longitude"])
        match = re.search(r'data-latitude="([^"]+)".*?data-longitude="([^"]+)"', html, re.DOTALL)
        if match:
            return float(match.group(1)), float(match.group(2))
        geo_match = re.search(r'<meta name="geo.position" content="([^;]+);([^"]+)">', html)
        if geo_match:
            return float(geo_match.group(1)), float(geo_match.group(2))
        return None, None

    def _extract_availability_text(self, description: str) -> str | None:
        match = re.search(r"\bavailable[^\n.]*", description, re.IGNORECASE)
        return match.group(0).strip() if match else None

    def _clean_posting_body(self, body_html: str) -> str:
        body = re.sub(r'<div class="print-information.*?</div>', "", body_html, flags=re.DOTALL)
        body = body.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        body = self._strip_tags(body)
        body = re.sub(r"QR Code Link to This Post", "", body, flags=re.IGNORECASE)
        body = re.sub(r"\n{3,}", "\n\n", unescape(body))
        return body.strip()

    def _strip_tags(self, value: str) -> str:
        return re.sub(r"<[^>]+>", "", value)

    def _looks_like_listing_url(self, url: str) -> bool:
        return re.search(r"/\d+\.html(?:\?|$)", url) is not None

    def _looks_like_listing_page(self, html: str) -> bool:
        return ('id="postingbody"' in html) or ('id="ld_posting_data"' in html)

    def _normalize_listing_url(self, url: str) -> str:
        parsed = urlparse(url)
        return parsed._replace(query="", fragment="").geturl()
