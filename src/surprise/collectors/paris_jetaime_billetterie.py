"""Collector for the Paris je t'aime ticketing (tourist office shop, tier 2: bookable offers).

Product pages come from the French sitemap ("/<category>-c<id>/<slug>-<id>"),
outside transport, bus tours and theme parks. Each page embeds its product in
the Nuxt state (__NUXT_DATA__): name, price, photo, text, address and category.
The page itself is where the product is booked.
"""

import re
import time as clock
from datetime import datetime
from typing import Any, Iterator

import httpx

from surprise.collectors.common import Normalized, run, safe_url
from surprise.collectors.facts import address_in_text, complete_place, lines, normalize_facts, nuxt_data, sitemap, utc_now
from surprise.models import RawRecord

SOURCE_ID = "paris_jetaime_billetterie"
BASE_URL = "https://ticket.parisjetaime.com"
SITEMAP = f"{BASE_URL}/__sitemap__/fr.xml"
IMAGE_URL = "https://pjt.imgix.net/"
USER_AGENT = "surprise-collector/0.1"
DELAY_SECONDS = 1.0

_PRODUCT = re.compile(r"^https://ticket\.parisjetaime\.com/[a-z0-9-]+-c(\d+)/[a-z0-9-]+-(\d+)$")
# Transport (c9), bus tours and excursions (c10), theme parks (c6).
_SKIPPED_CATEGORIES = {"6", "9", "10"}
_SKIPPED = re.compile(r"\bpass\b|carte annuelle|paris museum pass|transfert|aéroport|navette", re.IGNORECASE)


def fetch_product_urls(client: httpx.Client) -> list[str]:
    urls = [loc for loc, _ in sitemap(client, SITEMAP)]
    return list(dict.fromkeys(url for url in urls if (m := _PRODUCT.match(url)) and m.group(1) not in _SKIPPED_CATEGORIES))


def parse_product(url: str, page: str) -> dict[str, Any]:
    state = nuxt_data(page) or {}
    product = next((value for value in (state.get("data") or {}).values() if isinstance(value, dict) and "productId" in value), {})
    location = product.get("location") or {}
    category = (product.get("primaryCategory") or {}).get("name") or {}
    image = product.get("image")
    lead_text = "\n".join(filter(None, [_fr(product.get("excerpt")), lines(_fr(product.get("content")))])) or None
    return {
        "url": url,
        "product_id": product.get("productId"),
        "name": _fr(product.get("name")),
        # "52 Rue de l'Arbre Sec\r\n75001 Paris"; tours give their meeting point in the text only.
        "address": " ".join(str(location.get("address") or "").split()) or address_in_text(lead_text),
        "latitude": location.get("lat"),
        "longitude": location.get("lng"),
        "price_min": product.get("sellingPrice") or product.get("price"),
        "image_url": f"{IMAGE_URL}{image}?w=1400" if image else None,
        "category_text": _fr(category),
        "lead_text": lead_text,
        "website": url,
        "booking_url": url,
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(source_id=SOURCE_ID, external_id=url_id(payload["url"]), url=safe_url(payload["url"]), payload=payload)


def url_id(url: str) -> str:
    return url.rsplit("-", 1)[-1]


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    raw = to_raw_record(payload)
    if _SKIPPED.search(payload.get("name") or ""):
        return Normalized(raw, rejection="hors sujet")
    return normalize_facts(raw, payload, "Paris je t'aime", now)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for index, url in enumerate(fetch_product_urls(client)):
        if index:
            clock.sleep(delay)
        response = client.get(url)
        if response.status_code == 200:
            yield normalize(complete_place(parse_product(url, response.text)), now)


def _fr(value: Any) -> str:
    """A translated field: its French text."""
    if isinstance(value, dict):
        value = value.get("fr") or value.get("en")
    return str(value).strip() if value else ""


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
