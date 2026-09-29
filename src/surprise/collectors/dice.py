"""Collector for Dice (concerts and club nights ticketing, tier 2: bookable offers).

Events come from the sitemaps (robots.txt lists them): those of Paris end their
address with "-paris-tickets" and give their day in it ("…-23rd-oct-nouveau-casino-paris-tickets").
Those of the collection window are read soonest first, each from its page's
schema.org MusicEvent: name, start and end, venue with address and coordinates,
price, photo and description (lead_text). A night that ends after 2 am is a club
night, not a concert.
"""

import re
from datetime import date, datetime, timedelta
from typing import Any, Iterator

import httpx

from surprise.collectors.common import Normalized, page, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, ld_address, ld_node, normalize_facts, parse_datetime, sitemap, utc_now
from surprise.collectors.paris_zigzag import PARIS, WINDOW, _nearest_year
from surprise.models import RawRecord

SOURCE_ID = "dice"
BASE_URL = "https://dice.fm"
SITEMAP_INDEX = f"{BASE_URL}/sitemaps/sitemap.xml"
DELAY_SECONDS = 1.0

_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
# https://dice.fm/event/eowlyy-dews-pegahorn-23rd-oct-nouveau-casino-paris-tickets
_PARIS_EVENT = re.compile(r"^https://dice\.fm/event/([\w-]+?-(\d{1,2})(?:st|nd|rd|th)-([a-z]{3})-[\w-]*paris-tickets)$")
# Ends between 2 and 8 am: a night out.
_NIGHT_END = range(2, 9)


def fetch_events(client: httpx.Client, today: date, window: timedelta = WINDOW) -> list[str]:
    """Paris events of the window by the day in their address, soonest first."""
    events = []
    for child, _ in sitemap(client, SITEMAP_INDEX):
        for loc, _ in sitemap(client, child):
            if (match := _PARIS_EVENT.match(loc)) and (day := _day(match, today)) and today <= day <= today + window:
                events.append((day, loc))
    return [loc for _, loc in sorted(set(events))]


def parse_event(url: str, page: str) -> dict[str, Any]:
    event = ld_node(page, "Event")
    offers = event.get("offers") or []
    prices = [
        float(price)
        for offer in (offers if isinstance(offers, list) else [offers])
        for price in (offer.get("lowPrice"), offer.get("highPrice"), offer.get("price"))
        if price not in (None, "")
    ]
    image = event.get("image")
    starts_at, ends_at = parse_datetime(event.get("startDate")), parse_datetime(event.get("endDate"))
    night = bool(ends_at and ends_at.astimezone(PARIS).hour in _NIGHT_END and ends_at - (starts_at or ends_at) < timedelta(hours=16))
    kind = "soirée clubbing" if night else "concert" if event.get("@type") == "MusicEvent" else event.get("@type")
    return ld_address(event) | {
        "url": url,
        "slug": url.rsplit("/", 1)[-1],
        "name": event.get("name"),
        "starts_at": event.get("startDate"),
        "ends_at": event.get("endDate"),
        # A night ends the next day: its start is its session.
        "sessions": [event.get("startDate")] if event.get("startDate") else [],
        "price_min": min(prices) if prices else None,
        "price_max": max(prices) if prices else None,
        "free": bool(prices) and max(prices) == 0,
        "image_url": image[0] if isinstance(image, list) and image else image or None,
        "category_text": kind,
        "lead_text": event.get("description"),
        "website": url,
        "booking_url": url,
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(source_id=SOURCE_ID, external_id=payload["slug"], url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    raw = to_raw_record(payload)
    if not payload.get("name"):
        return Normalized(raw, rejection="page illisible")
    return normalize_facts(raw, payload, "Dice", now)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for url in fetch_events(client, now.astimezone(PARIS).date()):
        for payload in page(client, url, lambda r: parse_event(url, r.text), delay):
            yield normalize(payload, now)


def _day(match: re.Match[str], today: date) -> date | None:
    """The day of the address, of the year to come ("23rd-oct")."""
    day, month = int(match.group(2)), _MONTHS.get(match.group(3))
    if not month:
        return None
    try:
        return date(_nearest_year(day, month, today), month, day)
    except ValueError:
        return None


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
