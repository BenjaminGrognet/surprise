"""Collector for Tiqets (museum and attraction tickets, tier 2: bookable offers).

Paris products come from the French product sitemap (category "…-paris-c66746").
Each page gives a schema.org Product: name, price, photo, description. Pages
give no address: the place named in the product ("Billets pour Aquaboulevard :
billet d'entrée" → "Aquaboulevard") is located on OpenStreetMap.
"""

import re
from datetime import datetime
from typing import Any, Iterator

import httpx

from surprise.collectors.common import Normalized, page, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, complete_place, ld_node, normalize_facts, sitemap, utc_now
from surprise.models import RawRecord

SOURCE_ID = "tiqets"
SITEMAP = "https://www.tiqets.com/sitemap/site-map-product-fr.xml.gz"
DELAY_SECONDS = 1.0

_PARIS_PRODUCT = re.compile(r"^https://www\.tiqets\.com/fr/[\w-]*-paris-c66746/[\w-]+-p(\d+)/$")
_TICKET_WORDS = re.compile(r"^(?:billets?|entrée|visite|tickets?)\s+(?:pour|de|du|des|à|au)\s+(?:la |le |l')?", re.IGNORECASE)


def fetch_product_urls(client: httpx.Client) -> list[str]:
    return list(dict.fromkeys(loc for loc, _ in sitemap(client, SITEMAP) if _PARIS_PRODUCT.match(loc)))


def parse_product(url: str, page: str) -> dict[str, Any]:
    product = ld_node(page, "Product")
    offers = product.get("offers") or {}
    name = product.get("name") or ""
    place = _TICKET_WORDS.sub("", re.split(r"\s+[:–-]\s+", name)[0]).strip()
    image = product.get("image")
    return {
        "url": url,
        "product_id": _PARIS_PRODUCT.match(url).group(1),
        "name": name,
        "venue_name": place or None,
        "price_min": offers.get("price") or offers.get("lowPrice"),
        "image_url": image[0] if isinstance(image, list) and image else image,
        "lead_text": product.get("description"),
        "website": url,
        "booking_url": url,
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(source_id=SOURCE_ID, external_id=payload["product_id"], url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    raw = to_raw_record(payload)
    if not payload.get("name"):
        return Normalized(raw, rejection="page illisible")
    return normalize_facts(raw, payload, "Tiqets", now)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for url in fetch_product_urls(client):
        for payload in page(client, url, lambda r: complete_place(parse_product(url, r.text)), delay):
            yield normalize(payload, now)


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
