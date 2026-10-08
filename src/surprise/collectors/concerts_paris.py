"""Collector for concerts.paris (agenda of concerts, plays and exhibitions, tier 2: ticketing links).

The site publishes an open JSON feed for agents (https://concerts.paris/llms.txt):
events of Paris sorted by next date, 500 per page, 30 requests a minute. Each
event gives its venue (address, coordinates), dates, show dates, price, free or
paid, the official or ticketing link and a description (lead_text). The photo
is the one of the event page, served under a predictable URL.
"""

import time as clock
from datetime import datetime
from typing import Any, Iterator

import httpx

from surprise.collectors.common import Normalized, run, safe_url, with_reason
from surprise.collectors.facts import normalize_facts, utc_now
from surprise.models import RawRecord

SOURCE_ID = "concerts_paris"
FEED_URL = "https://api.concerts.paris/api/v1/geo-feed"
USER_AGENT = "surprise-collector/0.1"
# 30 requests a minute.
DELAY_SECONDS = 2.5
_GENRES = {
    "one-man-show": "humour stand-up",
    "cafe-theatre": "théâtre humour",
    "cirque-magie": "cirque spectacle",
    "comedie-musicale": "spectacle musical",
    "opera-lyrique": "opéra",
    "danse": "danse",
}


def fetch_events(client: httpx.Client, delay: float = DELAY_SECONDS) -> Iterator[dict[str, Any]]:
    """Paris events, the soonest first, page after page."""
    page = 1
    while True:
        response = client.get(FEED_URL, params={"niche": "concerts-paris", "city": "paris", "page": page})
        response.raise_for_status()
        data = response.json()
        yield from data.get("events") or []
        if not (data.get("pagination") or {}).get("events", {}).get("hasMore"):
            return
        page += 1
        clock.sleep(delay)


def to_raw_record(event: dict[str, Any]) -> RawRecord:
    return RawRecord(source_id=SOURCE_ID, external_id=event["slug"], url=safe_url(event.get("canonicalUrl")), payload=event)


def facts(event: dict[str, Any]) -> dict[str, Any]:
    venue = event.get("venue") or {}
    address = venue.get("address") or {}
    geo = venue.get("geo") or {}
    offers = event.get("offers") or {}
    practical = event.get("practical") or {}
    vertical = event.get("vertical") or "concert"
    genre = event.get("genre") or ""
    # A single date is an evening out; a run (plays, exhibitions) is a period.
    single = (event.get("startDate") or "")[:10] == (event.get("endDate") or "")[:10]
    return {
        "name": event.get("title"),
        "venue_name": venue.get("title"),
        "address": address.get("streetAddress"),
        "postal_code": address.get("postalCode"),
        "latitude": geo.get("latitude"),
        "longitude": geo.get("longitude"),
        "website": offers.get("officialUrl") or event.get("canonicalUrl"),
        # "url" is the site's tracked redirect to "officialUrl", given only when it is a ticketing.
        "booking_url": offers.get("officialUrl") if offers.get("url") else None,
        "image_url": f"https://media.concerts.paris/events/{event['slug']}.jpg",
        "starts_at": event.get("nextDate") if single else None,
        "starts_on": None if single else event.get("startDate"),
        "ends_on": None if single else event.get("endDate"),
        # A run's shows, to know which evenings it plays; sold out or cancelled ones are left out.
        "sessions": [
            show["startDate"]
            for show in event.get("showDates") or []
            if show.get("startDate")
            and show.get("eventStatus") != "EventCancelled"
            and (show.get("offers") or {}).get("availability") != "SoldOut"
        ],
        "price_min": offers.get("price"),
        "free": practical.get("priceType") == "gratuit",
        "price_label": practical.get("priceType"),
        "category_text": " ".join([{"expo": "exposition", "theatre": "théâtre"}.get(vertical, vertical), _GENRES.get(genre, genre)]),
        "audience": "jeune public" if genre == "jeune-public" else None,
        "lead_text": event.get("description"),
    }


def normalize(event: dict[str, Any], now: datetime) -> Normalized:
    raw = to_raw_record(event)
    cancelled = "annulé" if event.get("eventStatus") == "EventCancelled" else None
    return with_reason(cancelled, normalize_facts(raw, facts(event), now))


def collect(client: httpx.Client, now: datetime | None = None) -> Iterator[Normalized]:
    now = now or utc_now()
    for event in fetch_events(client):
        yield normalize(event, now)


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
