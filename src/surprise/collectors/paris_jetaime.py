"""Collector for Paris je t'aime (Paris tourist office agenda, tier 1: official, labelled sources).

The agenda (agenda.parisjetaime.com) is served by an open JSON API
(https://api.parisjetaime.com/openapi.json): events of Paris (département 75)
within the collection window, 20 per page, then each event's practical
information (hours, price, booking and official links). The API gives no photo:
the enrichment takes the official site's.
"""

import time as clock
from datetime import datetime
from typing import Any, Iterator

import httpx

from surprise.collectors.common import Normalized, euro_amounts, run, safe_url
from surprise.collectors.facts import normalize_facts, utc_now
from surprise.collectors.paris_zigzag import PARIS, WINDOW, is_evening
from surprise.models import RawRecord

SOURCE_ID = "paris_jetaime"
API_URL = "https://api.parisjetaime.com"
USER_AGENT = "surprise-collector/0.1"
PAGE_SIZE = 20
DELAY_SECONDS = 0.5
_CATEGORIES = {
    "expositions": "exposition",
    "concerts": "concert",
    "spectacles": "spectacle",
    "fetes-festivals": "festival",
    "foires-salons": "salon",
    "visites": "visite",
}


def fetch_events(client: httpx.Client, now: datetime, delay: float = DELAY_SECONDS) -> Iterator[dict[str, Any]]:
    """Events of the window, each with its practical information."""
    today = now.astimezone(PARIS).date()
    offset = 0
    while True:
        params = {
            "limit": PAGE_SIZE,
            "offset": offset,
            "departement": "75",
            "date_from": today.isoformat(),
            "date_to": (today + WINDOW).isoformat(),
            "min_score": 0,
        }
        response = client.get(f"{API_URL}/events", params=params)
        response.raise_for_status()
        data = response.json()
        for event in data.get("events") or []:
            clock.sleep(delay)
            detail = client.get(f"{API_URL}/events/{event['id']}")
            yield event | {"details": detail.json() if detail.status_code == 200 else {}}
        if not data.get("has_more"):
            return
        offset = data.get("next_offset") or offset + PAGE_SIZE


def to_raw_record(event: dict[str, Any]) -> RawRecord:
    url = event.get("url_wordpress") or event.get("source_url")
    return RawRecord(source_id=SOURCE_ID, external_id=event["id"], url=safe_url(url), payload=event)


def facts(event: dict[str, Any]) -> dict[str, Any]:
    practical = (event.get("details") or {}).get("infos_pratiques") or {}
    price_text = " ".join(filter(None, [event.get("price_type"), practical.get("tarif")]))
    amounts = euro_amounts(price_text)
    reservation = practical.get("reservation")
    official = practical.get("lien_officiel") or event.get("source_url")
    return {
        "name": event.get("title"),
        "venue_name": event.get("venue_name"),
        "address": event.get("venue_address") or practical.get("adresse"),
        "postal_code": event.get("zipcode"),
        "website": official,
        "booking_url": reservation if safe_url(reservation) else None,
        "starts_on": event.get("start_date"),
        "ends_on": event.get("end_date"),
        "evening": is_evening(practical.get("horaires") or ""),
        "free": "gratuit" in price_text.lower() and not any(amounts),
        "price_min": amounts[0] if amounts else event.get("price_min") or None,
        "price_max": amounts[-1] if amounts else None,
        "price_label": price_text,
        "category_text": " ".join(_CATEGORIES.get(c, c) for c in event.get("categories") or []),
        "tags": event.get("tags"),
        "audience": " ".join(event.get("audience") or []) if isinstance(event.get("audience"), list) else event.get("audience"),
    }


def normalize(event: dict[str, Any], now: datetime) -> Normalized:
    return normalize_facts(to_raw_record(event), facts(event), "Paris je t'aime", now)


def collect(client: httpx.Client, now: datetime | None = None) -> Iterator[Normalized]:
    now = now or utc_now()
    for event in fetch_events(client, now):
        yield normalize(event, now)


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
