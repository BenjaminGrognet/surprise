"""Collector for Shotgun (club nights, concerts and festivals ticketing, tier 2: bookable offers).

Events are discovered on the Paris page, soonest first: it is cumulative
(`?page=N` lists the first (N+1)×14 events), so it is asked larger and larger
until it has no next page. Each event is read from its page's schema.org
MusicEvent: name, start and end, venue with address and coordinates, price,
photo and description (lead_text). Reading stops once the events leave the
collection window. The site answers bots with a 429: requests look like a
browser's, one a second.
"""

import re
import time as clock
from datetime import datetime
from typing import Any, Iterator

import httpx

from surprise.collectors.common import Normalized, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, ld_address, ld_node, normalize_facts, utc_now
from surprise.models import RawRecord

SOURCE_ID = "shotgun"
BASE_URL = "https://shotgun.live"
PARIS_PAGE = f"{BASE_URL}/fr/cities/paris"
MAX_PAGE = 1600  # about 22,000 events: far beyond Paris's
DELAY_SECONDS = 1.0
# Events are listed by date: after this many beyond the window in a row, the rest is too.
OUT_OF_WINDOW_STOP = 20

_EVENT = re.compile(r'href="/fr/events/([\w-]+)"')


def fetch_event_slugs(client: httpx.Client, delay: float = DELAY_SECONDS) -> list[str]:
    """Events of the Paris page, soonest first, each once."""
    page = 25
    while True:
        response = client.get(PARIS_PAGE, params={"page": page})
        response.raise_for_status()
        if f"page={page + 1}" not in response.text or page >= MAX_PAGE:
            return list(dict.fromkeys(_EVENT.findall(response.text)))
        page *= 2
        clock.sleep(delay)


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
    beyond = 0
    for slug in fetch_event_slugs(client, delay):
        clock.sleep(delay)
        response = client.get(f"{BASE_URL}/fr/events/{slug}")
        if response.status_code != 200:
            continue
        normalized = normalize(parse_event(slug, response.text), now)
        yield normalized
        beyond = beyond + 1 if normalized.rejection == "hors fenêtre" else 0
        if beyond >= OUT_OF_WINDOW_STOP:
            return


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
