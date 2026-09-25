"""Collector for BilletRéduc (discounted tickets for shows, tier 2: bookable offers).

Shows are discovered on the Paris page (links "/spectacle/<slug>-<id>") and
read from their page's schema.org Event (its script type is written
"application/ld&#x2B;json"): name, first and last show, venue with address,
prices, photo and description (lead_text).
"""

import re
import time as clock
from datetime import datetime
from typing import Any, Iterator

import httpx

from surprise.collectors.common import Normalized, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, parse_datetime, ld_address, ld_node, normalize_facts, utc_now
from surprise.collectors.paris_zigzag import PARIS
from surprise.models import RawRecord

SOURCE_ID = "billetreduc"
BASE_URL = "https://www.billetreduc.com"
LIST_URL = f"{BASE_URL}/paris/"
DELAY_SECONDS = 1.0

_SHOW = re.compile(r'href="(?:https://www\.billetreduc\.com)?(/spectacle/[\w-]+-\d+)"')


def fetch_show_urls(client: httpx.Client) -> list[str]:
    response = client.get(LIST_URL)
    response.raise_for_status()
    return [BASE_URL + path for path in dict.fromkeys(_SHOW.findall(response.text))]


def parse_show(url: str, page: str) -> dict[str, Any]:
    event = ld_node(page, "Event")
    offers = event.get("offers") or []
    offers = offers if isinstance(offers, list) else [offers]
    prices = [float(p) for o in offers for p in (o.get("lowPrice"), o.get("price"), o.get("highPrice")) if p not in (None, "")]
    image = event.get("image")
    first, last = parse_datetime(event.get("startDate")), parse_datetime(event.get("endDate"))
    single = bool(first and last and first == last) or not last
    return ld_address(event) | {
        "url": url,
        "show_id": url.rsplit("-", 1)[-1],
        "name": event.get("name"),
        "starts_at": event.get("startDate") if single else None,
        "starts_on": None if single else event.get("startDate"),
        "ends_on": None if single else event.get("endDate"),
        # A run of shows: their time says whether it is an evening out.
        "evening": first.astimezone(PARIS).hour >= 19 if first else None,
        "price_min": min(prices) if prices else None,
        "price_max": max(prices) if prices else None,
        "image_url": image[0] if isinstance(image, list) and image else image,
        "category_text": "spectacle théâtre",
        "lead_text": event.get("description"),
        "website": url,
        "booking_url": url,
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(source_id=SOURCE_ID, external_id=payload["show_id"], url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    raw = to_raw_record(payload)
    if not payload.get("name"):
        return Normalized(raw, rejection="page illisible")
    return normalize_facts(raw, payload, "BilletRéduc", now)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for index, url in enumerate(fetch_show_urls(client)):
        if index:
            clock.sleep(delay)
        response = client.get(url)
        if response.status_code == 200:
            yield normalize(parse_show(url, response.text), now)


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
