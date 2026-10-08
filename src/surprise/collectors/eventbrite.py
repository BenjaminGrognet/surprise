"""Collector for Eventbrite (events ticketing, tier 2: bookable offers).

The Paris search pages ("/d/france--paris/events/?page=N") list their events
as a schema.org ItemList: name, dates, photo, venue with address and
coordinates, page. Each event page adds its price and description (lead_text)
from its own schema.org Event. Online events, singles' nights and professional
events are left out.
"""

import time as clock
from datetime import datetime
from typing import Any, Iterator

import httpx

from surprise.collectors.common import Normalized, page, run, safe_url, with_reason
from surprise.collectors.facts import BROWSER_HEADERS, ld_address, ld_node, normalize_facts, utc_now
from surprise.models import RawRecord

SOURCE_ID = "eventbrite"
# Pages read less than this many days ago are not read again: dated events, soon sold out or rescheduled.
FRESH_DAYS = 2
SEARCH_URL = "https://www.eventbrite.fr/d/france--paris/events/"
DELAY_SECONDS = 1.0
MAX_PAGES = 30


def fetch_events(client: httpx.Client, delay: float = DELAY_SECONDS) -> Iterator[dict[str, Any]]:
    seen: set[str] = set()
    for number in range(1, MAX_PAGES + 1):
        response = client.get(SEARCH_URL, params={"page": number})
        if response.status_code != 200:
            return
        items = [element.get("item") or {} for element in ld_node(response.text, "ItemList").get("itemListElement") or []]
        new = [item for item in items if item.get("url") and item["url"] not in seen]
        if not new:
            return
        for item in new:
            seen.add(item["url"])
            yield item
        clock.sleep(delay)


def parse_event(item: dict[str, Any], page: str | None) -> dict[str, Any]:
    event = ld_node(page or "", "Event") or item
    offers = event.get("offers") or []
    offers = offers if isinstance(offers, list) else [offers]
    prices = [float(p) for o in offers for p in (o.get("lowPrice"), o.get("price"), o.get("highPrice")) if p not in (None, "")]
    return ld_address(item) | {
        "url": item["url"],
        "event_id": item["url"].rstrip("/").rsplit("-", 1)[-1],
        "name": item.get("name"),
        "starts_at": event.get("startDate") if "T" in str(event.get("startDate")) else None,
        "starts_on": item.get("startDate"),
        "ends_on": item.get("endDate"),
        "price_min": min(prices) if prices else None,
        "price_max": max(prices) if prices else None,
        "free": bool(prices) and max(prices) == 0,
        "image_url": event.get("image") if isinstance(event.get("image"), str) else item.get("image"),
        "category_text": event.get("@type") if isinstance(event.get("@type"), str) else None,
        "online": "Online" in str(event.get("eventAttendanceMode")),
        "lead_text": event.get("description"),
        "website": item["url"],
        "booking_url": item["url"],
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(source_id=SOURCE_ID, external_id=payload["event_id"], url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    raw = to_raw_record(payload)
    # A single-day event starts on its start time; the dates of a run give its period.
    single = payload.get("starts_on") == payload.get("ends_on") or not payload.get("ends_on")
    facts = payload | ({"starts_on": None, "ends_on": None} if single and payload.get("starts_at") else {})
    return with_reason("en ligne" if payload.get("online") else None, normalize_facts(raw, facts, now))


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for item in fetch_events(client, delay):
        # Unreadable, the event keeps what the listing says.
        for payload in page(client, item["url"], lambda r: parse_event(item, r.text), delay) or [parse_event(item, None)]:
            yield normalize(payload, now)


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
