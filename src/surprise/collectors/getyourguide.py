"""Collector for GetYourGuide (tours, tickets and experiences, tier 2: bookable offers).

Paris activities ("/fr-fr/paris-l16/<slug>-t<id>/") are found in the French
activity sitemaps, read one after the other until enough are found. Each page
gives a schema.org Product/TouristTrip (name, lowest price, photos, description,
itinerary). The meeting point comes with its coordinates (its Google Maps link),
else it is the first Paris address in the page; its postcode comes from OpenStreetMap.
"""

import html
import re
import time as clock
from datetime import datetime
from typing import Any, Iterator

import httpx

from surprise.collectors.common import Normalized, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, address_in_text, complete_place, ld_node, normalize_facts, sitemap, text, utc_now
from surprise.models import RawRecord

SOURCE_ID = "getyourguide"
SITEMAP_INDEX = "https://www.getyourguide.com/fr-fr/sitemap.xml"
DELAY_SECONDS = 1.0

_MEETING_POINT = re.compile(
    r'id="meeting-point-links".*?<span[^>]*><span[^>]*>([^<]*)</span>.*?maps\.google\.com/\?q=@(-?[\d.]+),(-?[\d.]+)', re.DOTALL
)
_PARIS_ACTIVITY = re.compile(r"^https://www\.getyourguide\.(?:com|fr)/fr-fr/paris-l16/[\w-]+-t(\d+)/$")


def fetch_activity_urls(client: httpx.Client, delay: float = DELAY_SECONDS) -> Iterator[str]:
    for child, _ in sitemap(client, SITEMAP_INDEX):
        if "sitemap-activity" not in child:
            continue
        clock.sleep(delay)
        for loc, _ in sitemap(client, child):
            if _PARIS_ACTIVITY.match(loc):
                yield loc


def parse_activity(url: str, page: str) -> dict[str, Any]:
    product = ld_node(page, "Product", "TouristTrip")
    offers = product.get("offers") or {}
    meeting = _MEETING_POINT.search(page)
    images = product.get("image") or []
    return {
        "url": url,
        "activity_id": _PARIS_ACTIVITY.match(url).group(1),
        "name": product.get("name"),
        "venue_name": html.unescape(meeting.group(1)).strip(" .") or None if meeting else None,
        "latitude": meeting.group(2) if meeting else None,
        "longitude": meeting.group(3) if meeting else None,
        "address": None if meeting else address_in_text(text(page)),
        "price_min": offers.get("lowPrice") or offers.get("price"),
        "image_url": images[0] if isinstance(images, list) and images else images or None,
        "lead_text": product.get("description"),
        "website": url,
        "booking_url": url,
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(source_id=SOURCE_ID, external_id=payload["activity_id"], url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    raw = to_raw_record(payload)
    if not payload.get("name"):
        return Normalized(raw, rejection="page illisible")
    # "Paris : croisière aux lueurs du soir…"
    name = re.sub(r"^Paris\s*:\s*", "", payload["name"]).strip()
    return normalize_facts(raw, payload | {"name": name[:1].upper() + name[1:]}, "GetYourGuide", now)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for url in fetch_activity_urls(client, delay):
        clock.sleep(delay)
        response = client.get(url)
        if response.status_code == 200:
            yield normalize(complete_place(parse_activity(url, response.text)), now)


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
