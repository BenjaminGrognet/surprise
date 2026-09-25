"""Collector for Civitatis (guided tours and tickets, tier 2: bookable offers).

Activity pages come from the French sitemap, Paris ones by their URL
("/fr/paris/<slug>/"). Each page gives a schema.org Product (name, price,
photos, description) and, in the state of its Next.js page, the meeting point
with its coordinates; its postcode comes from OpenStreetMap.
"""

import re
import time as clock
from datetime import datetime
from typing import Any, Iterator

import httpx

from surprise.collectors.common import Normalized, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, complete_place, ld_node, lines, normalize_facts, sitemap, utc_now
from surprise.models import RawRecord

SOURCE_ID = "civitatis"
BASE_URL = "https://www.civitatis.com"
SITEMAP = f"{BASE_URL}/sitemap_fr.xml"
DELAY_SECONDS = 1.0

_ACTIVITY = re.compile(r"^https://www\.civitatis\.com/fr/paris/([\w-]+)/$")
# Pages of the city that are not activities.
_NOT_ACTIVITY = re.compile(r"^(?:transferts?|excursions?|visites-guidees|billets|activites|croisieres)$")
# \"address\":\"\",\"short_address\":\"Aquarium de Paris.\",\"gps\":{\"latitude\":48.86,\"longitude\":2.29}
_MEETING_POINT = re.compile(
    r'\\"address\\":\\"([^\\"]*)\\",(?:\\"short_address\\":\\"([^\\"]*)\\",)?\\"gps\\":\{\\"latitude\\":(-?[\d.]+),\\"longitude\\":(-?[\d.]+)'
)


def fetch_activity_urls(client: httpx.Client) -> list[str]:
    urls = [loc for loc, _ in sitemap(client, SITEMAP)]
    return list(dict.fromkeys(url for url in urls if (m := _ACTIVITY.match(url)) and not _NOT_ACTIVITY.match(m.group(1))))


def parse_activity(url: str, page: str) -> dict[str, Any]:
    product = ld_node(page, "Product")
    offers = product.get("offers") or {}
    meeting = _MEETING_POINT.search(page)
    images = product.get("image") or []
    return {
        "url": url,
        "slug": url.rstrip("/").rsplit("/", 1)[-1],
        "name": product.get("name"),
        "venue_name": (meeting.group(2) or meeting.group(1)).strip(" .") or None if meeting else None,
        "latitude": meeting.group(3) if meeting else None,
        "longitude": meeting.group(4) if meeting else None,
        "price_min": offers.get("price") or offers.get("lowPrice"),
        "image_url": images[0] if isinstance(images, list) and images else images or None,
        "lead_text": lines(product.get("description")),
        "website": url,
        "booking_url": url,
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(source_id=SOURCE_ID, external_id=payload["slug"], url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    raw = to_raw_record(payload)
    if not payload.get("name"):
        # A page of activities ("balades-bateau"), not an activity.
        return Normalized(raw, rejection="page de catégorie")
    return normalize_facts(raw, payload, "Civitatis", now)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for index, url in enumerate(fetch_activity_urls(client)):
        if index:
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
