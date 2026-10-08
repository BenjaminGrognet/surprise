"""Collector for Fever (experiences and shows ticketing, tier 2: bookable offers).

Plans are discovered on the Paris page (links "/m/<id>") and read from their
page's schema.org Event: name, dates, photo, venue name and coordinates, lowest
price, description (lead_text). The arrondissement comes from the description
("Lieu : Maison de l'Océan (Paris 5)"), else from the coordinates on OpenStreetMap.
"""

import re
from datetime import datetime
from typing import Any, Iterator

import httpx

from surprise.collectors.common import Normalized, page, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, complete_place, ld_node, normalize_facts, utc_now
from surprise.models import RawRecord

SOURCE_ID = "fever"
# Pages read less than this many days ago are not read again: dated events, soon sold out or rescheduled.
FRESH_DAYS = 2
BASE_URL = "https://feverup.com"
CITY_PAGES = [f"{BASE_URL}/fr/paris"]
DELAY_SECONDS = 1.0

_PLAN = re.compile(r'href="(?:https://feverup\.com)?(?:/fr)?/m/(\d+)')
_DISTRICT = re.compile(r"\(Paris\s*(\d{1,2})(?:e|er|ème)?\)", re.IGNORECASE)


def fetch_plan_ids(client: httpx.Client) -> list[str]:
    ids: list[str] = []
    for url in CITY_PAGES:
        response = client.get(url)
        response.raise_for_status()
        ids += _PLAN.findall(response.text)
    return list(dict.fromkeys(ids))


def parse_plan(plan_id: str, page: str) -> dict[str, Any]:
    event = ld_node(page, "Event") or ld_node(page, "Product")
    location = event.get("location") or {}
    geo = location.get("geo") or {}
    offers = event.get("offers") or []
    prices = [float(offer["price"]) for offer in (offers if isinstance(offers, list) else [offers]) if offer.get("price") not in (None, "")]
    description = event.get("description") or ""
    district = _DISTRICT.search(description)
    image = event.get("image")
    return {
        "url": f"{BASE_URL}/fr/m/{plan_id}",
        "plan_id": plan_id,
        "name": event.get("name"),
        "venue_name": location.get("name"),
        "address": ((location.get("address") or {}).get("streetAddress")),
        "postal_code": f"750{int(district.group(1)):02d}" if district and 1 <= int(district.group(1)) <= 20 else None,
        "latitude": geo.get("latitude"),
        "longitude": geo.get("longitude"),
        "starts_on": event.get("startDate"),
        "ends_on": event.get("endDate"),
        "price_min": min(prices) if prices else None,
        "price_max": max(prices) if prices else None,
        "image_url": image.get("contentUrl") if isinstance(image, dict) else image,
        "lead_text": description or None,
        "website": f"{BASE_URL}/fr/m/{plan_id}",
        "booking_url": f"{BASE_URL}/fr/m/{plan_id}",
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(source_id=SOURCE_ID, external_id=payload["plan_id"], url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    raw = to_raw_record(payload)
    if not payload.get("name"):
        # Series pages (Candlelight…) list plans of several venues without schema.org data.
        return Normalized(raw, rejection="page de série")
    return normalize_facts(raw, payload, now)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for plan_id in fetch_plan_ids(client):
        for payload in page(client, f"{BASE_URL}/m/{plan_id}", lambda r: complete_place(parse_plan(plan_id, r.text)), delay):
            yield normalize(payload, now)


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
