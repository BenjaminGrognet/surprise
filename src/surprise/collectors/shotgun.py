"""Collector for Shotgun (club nights, concerts and festivals ticketing, tier 2: bookable offers).

Events are discovered on the Paris pages (the city and its music genres, listed
in the "cities/music-genres" sitemap) and read from their page's schema.org
MusicEvent: name, start and end, venue with address and coordinates, price,
photo and description (lead_text). The site answers bots with a 429: requests
look like a browser's, one a second.
"""

import re
import time as clock
from datetime import datetime
from typing import Any, Iterator

import httpx

from surprise.collectors.common import Normalized, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, ld_address, ld_node, normalize_facts, sitemap, utc_now
from surprise.models import RawRecord

SOURCE_ID = "shotgun"
BASE_URL = "https://shotgun.live"
GENRES_SITEMAP = f"{BASE_URL}/api/sitemaps/cities/music-genres/sitemap/0.xml"
DELAY_SECONDS = 1.0

_EVENT = re.compile(r'href="/fr/events/([\w-]+)"')
_PARIS_PAGE = re.compile(r"^https://shotgun\.live/(?:en|fr)/cities/paris(?:/[\w-]+)?$")


def fetch_event_slugs(client: httpx.Client, delay: float = DELAY_SECONDS) -> Iterator[str]:
    """Events of the Paris page, then of its genre pages, each once."""
    try:
        genre_pages = [loc for loc, _ in sitemap(client, GENRES_SITEMAP) if _PARIS_PAGE.match(loc)]
    except httpx.HTTPError:
        genre_pages = []
    pages = [f"{BASE_URL}/fr/cities/paris"] + sorted({re.sub(r"/en/", "/fr/", page) for page in genre_pages})
    seen: set[str] = set()
    for page in dict.fromkeys(pages):
        response = client.get(page)
        clock.sleep(delay)
        if response.status_code != 200:
            continue
        for slug in _EVENT.findall(response.text):
            if slug not in seen:
                seen.add(slug)
                yield slug


def parse_event(slug: str, page: str) -> dict[str, Any]:
    event = ld_node(page, "Event")
    offers = event.get("offers") or []
    prices = [float(o["price"]) for o in (offers if isinstance(offers, list) else [offers]) if o.get("price") not in (None, "")]
    place = ld_address(event)
    image = event.get("image")
    return place | {
        "url": f"{BASE_URL}/fr/events/{slug}",
        "slug": slug,
        "name": event.get("name"),
        "starts_at": event.get("startDate"),
        "ends_at": event.get("endDate"),
        "price_min": min(prices) if prices else None,
        "price_max": max(prices) if prices else None,
        "free": bool(prices) and max(prices) == 0,
        "image_url": image[0] if isinstance(image, list) else image,
        "category_text": "concert" if event.get("@type") == "MusicEvent" and "festival" not in slug else "soirée",
        "lead_text": event.get("description"),
        "website": f"{BASE_URL}/fr/events/{slug}",
        "booking_url": f"{BASE_URL}/fr/events/{slug}",
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(source_id=SOURCE_ID, external_id=payload["slug"], url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    raw = to_raw_record(payload)
    if not payload.get("name"):
        return Normalized(raw, rejection="page illisible")
    return normalize_facts(raw, payload, "Shotgun", now)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for slug in fetch_event_slugs(client, delay):
        clock.sleep(delay)
        response = client.get(f"{BASE_URL}/fr/events/{slug}")
        if response.status_code == 200:
            yield normalize(parse_event(slug, response.text), now)


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
