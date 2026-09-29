"""Collector for Wecandoo (craft workshops with artisans, tier 2: bookable offers).

Workshop pages come from the sitemap, Paris ones by their URL ("/atelier/paris-…").
Each page embeds the workshop as JSON in its Vue props (":page-props"): name,
price and for how many, duration, audience, place (address, coordinates),
photos and the course of the workshop (lead_text). The page is where it is booked.
Bots get a prerendered page without these props: requests look like a browser's.
"""

import html
import json
import re
from datetime import datetime
from typing import Any, Iterator

import httpx

from surprise.collectors.common import Normalized, page, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, lines, normalize_facts, sitemap, utc_now
from surprise.models import RawRecord

SOURCE_ID = "wecandoo"
BASE_URL = "https://wecandoo.fr"
SITEMAP = f"{BASE_URL}/sitemap.xml"
DELAY_SECONDS = 1.0

_PARIS_WORKSHOP = re.compile(r"^https://wecandoo\.fr/atelier/paris-[\w-]+$")
_PROPS = re.compile(r':page-props="([^"]*)"')


def fetch_workshop_urls(client: httpx.Client) -> list[str]:
    return list(dict.fromkeys(loc for loc, _ in sitemap(client, SITEMAP) if _PARIS_WORKSHOP.match(loc)))


def parse_workshop(url: str, page: str) -> dict[str, Any]:
    match = _PROPS.search(page)
    workshop = (json.loads(html.unescape(match.group(1))) if match else {}).get("workshop") or {}
    place = workshop.get("lieu") or {}
    address = place.get("address") or {}
    workshop_format = workshop.get("format") or {}
    tags = [tag.get("slug") for tag in workshop.get("tags") or [] if tag.get("slug")]
    return {
        "url": url,
        "workshop_id": workshop.get("id"),
        "name": workshop.get("nom"),
        "venue_name": place.get("nom"),
        "address": " ".join(filter(None, [address.get("address1"), address.get("address2")])),
        "postal_code": address.get("zip_code"),
        "latitude": place.get("lat"),
        "longitude": place.get("lng"),
        "price_min": workshop.get("prix"),
        # "duo" workshops are priced for two.
        "per_couple": workshop_format.get("price_for") == "duo",
        "duration_minutes": workshop.get("duration"),
        "image_url": next(iter(workshop.get("images") or []), None),
        "category_text": " ".join(filter(None, ["atelier", (workshop.get("craft") or {}).get("label")])),
        "tags": tags,
        "audience": " ".join(filter(None, [workshop_format.get("name"), "enfant" if (workshop.get("age_max") or 99) < 18 else None])),
        "lead_text": lines(" ".join(filter(None, [workshop.get("sous_titre"), workshop.get("deroulement_atelier")]))),
        "website": url,
        "booking_url": url,
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    slug = payload["url"].rsplit("/", 1)[-1]
    return RawRecord(source_id=SOURCE_ID, external_id=slug, url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    raw = to_raw_record(payload)
    if "duo-parent-enfant" in (payload.get("tags") or []):
        return Normalized(raw, rejection="jeune public")
    return normalize_facts(raw, payload | {"tags": None}, "Wecandoo", now)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for url in fetch_workshop_urls(client):
        for payload in page(client, url, lambda r: parse_workshop(url, r.text), delay):
            yield normalize(payload, now)


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
