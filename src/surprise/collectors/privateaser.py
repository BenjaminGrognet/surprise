"""Collector for Privateaser (bars booked online for a group, tier 2: bookable offers).

Bars of Paris that take a booking for a few tables, free, or privatise a room:
what a band of friends (Secret Squad) needs for its drinks, where a bar without
booking leaves a band of six waiting at the door. They come from the site's list
of bars to book in Paris (robots.txt allows it), page by page, the most booked
first. Each bar's page marks its place in schema.org microdata (name, address,
postcode, coordinates, opening hours, photos) and lists its booking options with
their capacity ("Réserver quelques tables 1-440 personnes", "Privatiser Salon
1-30 personnes"): the smallest and the largest party it takes. Its kinds
("Bar dansant", "Brasserie moderne") say what it is, its description is kept as
lead_text for Claude to rewrite (to remove before any public use). Booking a
few tables costs nothing; the booking itself (/booking/) is closed to robots, so
it is not checked. The site blocks a robot reading fast: ten seconds between two
pages, and the run stops when pages no longer answer.
"""

import html
import re
import time as clock
from datetime import datetime
from typing import Any, Iterator

import httpx

from surprise.collectors.common import Normalized, page, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, lines, normalize_facts, text, utc_now
from surprise.models import RawRecord

SOURCE_ID = "privateaser"
# Pages read less than this many days ago are not read again: venues, which rarely change.
FRESH_DAYS = 30
BASE_URL = "https://www.privateaser.com"
LISTING = f"{BASE_URL}/reservation-bar/top-reserver-bars-paris"
# A guard: the list has about a hundred pages of thirty bars.
MAX_PAGES = 150
# Its CloudFront blocks a robot that reads faster (403 "Request blocked", seen at about fifty pages in five minutes).
DELAY_SECONDS = 10.0
# Pages in a row that do not answer: blocked, the run stops there.
BLOCKED_AFTER = 3

_VENUE = re.compile(r'href="(https://www\.privateaser\.com/lieu/\d+-[\w-]+)"')
_VENUE_ID = re.compile(r"/lieu/(\d+)-")
_NAME = re.compile(r'<h1 itemprop="name">(.*?)</h1>', re.DOTALL)
_META = r'<meta itemprop="{}" content="([^"]*)"'
_LABEL = re.compile(r'<div class="concept-label[^"]*">([^<]+)</div>')
_HOURS = re.compile(r'itemprop="openingHours"[^>]*content="([^"]+)"')
_OPTION = re.compile(r'<h3 class="title">(.*?)</h3>\s*<div class="capacity-block">\s*(\d+)\s*-\s*(\d+)\s*personnes', re.DOTALL)
_DESCRIPTION = re.compile(r'<div class="offering-seo-description[^"]*">(.*?)</div>', re.DOTALL)
_OG_IMAGE = re.compile(r'<meta property="og:image" content="([^"]+)"')
# "Mo-We 07:30-01:00": open past 9 pm, or past midnight.
_RANGE = re.compile(r"(\d{2}):(\d{2})-(\d{2}):(\d{2})")


def venue_urls(client: httpx.Client, delay: float = DELAY_SECONDS) -> Iterator[str]:
    """The bars of the list, page after page, each once; a page that adds none ends it."""
    seen: set[str] = set()
    for number in range(1, MAX_PAGES + 1):
        if number > 1:
            clock.sleep(delay)
        try:
            response = client.get(LISTING, params={"page": number})
        except httpx.HTTPError:
            return
        found = [url for url in _VENUE.findall(response.text) if url not in seen] if response.status_code == 200 else []
        if not found:
            return
        for url in dict.fromkeys(found):
            seen.add(url)
            yield url


def parse_venue(url: str, page: str) -> dict[str, Any] | None:
    """A bar's facts, or None for a page without its name."""
    name = _NAME.search(page)
    if not name:
        return None
    options = [(text(title), int(low), int(high)) for title, low, high in _OPTION.findall(page)]
    hours = _HOURS.findall(page)
    description = _DESCRIPTION.search(page)
    image = _OG_IMAGE.search(page)
    labels = [text(label) for label in _LABEL.findall(page)]
    return {
        "url": url,
        "venue_id": venue.group(1) if (venue := _VENUE_ID.search(url)) else url,
        "name": text(name.group(1)),
        "address": _meta("streetAddress", page),
        "postal_code": _meta("postalCode", page),
        "latitude": _meta("latitude", page),
        "longitude": _meta("longitude", page),
        "labels": labels,
        "hours": hours,
        "evening": is_evening(hours) if hours else None,
        "options": [f"{title} {low}-{high}" for title, low, high in options],
        "players_min": min(low for _, low, _ in options) if options else None,
        "players_max": max(high for _, _, high in options) if options else None,
        "image_url": html.unescape(image.group(1)) if image else None,
        # The organiser's text, for Claude to rewrite a description.
        "lead_text": lines(description.group(1)) if description else None,
    }


def is_venue(url: str) -> bool:
    """A bar's page: "https://www.privateaser.com/lieu/1608-le-capitole-cafe"."""
    return bool(re.match(r"https://www\.privateaser\.com/lieu/\d+-", url))


def is_evening(hours: list[str]) -> bool:
    """Open in the evening: one of its ranges ends after 9 pm or past midnight."""
    for opening_hour, _, closing_hour, closing_minute in _RANGE.findall(" ".join(hours)):
        closing = int(closing_hour) * 60 + int(closing_minute)
        if closing >= 21 * 60 or closing < int(opening_hour) * 60:
            return True
    return False


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(source_id=SOURCE_ID, external_id=payload["venue_id"], url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    facts = payload | {
        "venue_name": payload["name"],
        # A bar, whatever else it is: "Brasserie moderne", "Bar dansant".
        "category_text": " ".join(["bar", *(payload.get("labels") or [])]),
        "website": payload["url"],
        "booking_url": payload["url"],
    }
    result = normalize_facts(to_raw_record(payload), facts, "Privateaser", now)
    if result.activity:
        # Booking a few tables is free: the drinks are paid there.
        result.activity.offers[0].paid_booking = False
    return result


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    unanswered = 0
    for url in venue_urls(client, delay):
        payloads = page(client, url, lambda r: parse_venue(url, r.text), delay)
        unanswered = 0 if payloads else unanswered + 1
        if unanswered >= BLOCKED_AFTER:
            print(f"{BLOCKED_AFTER} pages sans réponse de suite : bloqué par le site, arrêt")
            return
        for payload in payloads:
            yield normalize(payload, now)


def _meta(prop: str, page: str) -> str | None:
    match = re.search(_META.format(prop), page)
    return html.unescape(match.group(1)).strip() or None if match else None


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
