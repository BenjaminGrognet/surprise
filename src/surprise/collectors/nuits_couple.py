"""Collector for nights for two in Paris: love rooms, secret rooms, suites with a private spa, unusual hotels.

Three catalogues give one page per room, each with a schema.org LodgingBusiness
(name, address, coordinates, photos, price of the night):
- Loveroomers: the listings of Paris from the sitemaps, booked on booking.loveroomers.fr;
- Love'nSpa (Shopify): the "paris" collection (products.json), booked on the product page;
- Love Île-de-France: the rooms linked from its Paris page (no online booking seen yet).
Four guides list unusual or romantic nights (Love Room Guide, The Love Room,
Cupiroom, Weekendlove): one idea per heading, as in selections_couple, located
on OpenStreetMap by its name. Rooms outside Paris intra-muros are rejected.
"""

import html
import re
from datetime import datetime
from typing import Any, Iterator
from urllib.parse import urlsplit

import httpx

from surprise.collectors.common import Normalized, page, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, complete_place, ld_node, lines, normalize_facts, sitemap, utc_now
from surprise.collectors.paris_zigzag import _slug
from surprise.collectors.selections_couple import parse_article
from surprise.models import RawRecord

SOURCE_ID = "nuits_couple"
# Pages read less than this many days ago are not read again: venues, which rarely change.
FRESH_DAYS = 30
DELAY_SECONDS = 1.0
LOVEROOMERS_SITEMAPS = [f"https://www.loveroomers.fr/job_listing-sitemap{n}.xml" for n in (1, 2)]
LOVENSPA_PRODUCTS = "https://lovenspa.fr/collections/paris/products.json?limit=250"
LOVE_IDF_PARIS = "https://love-iledefrance.fr/love-room-paris/"
GUIDES = [
    "https://loveroomguide.fr/magazine/meilleures-love-rooms-paris",
    "https://the-love-room.com/nuit-insolite-paris/",
    "https://www.cupiroom.fr/nuit-insolite-amoureux-paris/",
    "https://weekendlove.fr/6-hotels-pour-couples-a-paris/",
]
# Loveroomers: /<kind>/<département>/<city>/<room>/, Paris rooms under the "paris" département.
_LOVEROOMERS_PARIS = re.compile(r"^https://www\.loveroomers\.fr/[\w-]+/paris/[\w-]+/[\w-]+/$")
_LOVEROOMERS_BOOKING = re.compile(r'href="(https://booking\.loveroomers\.fr/[^"\s%]+)')
_LOVE_IDF_ROOM = re.compile(r'href="(https://love-iledefrance\.fr/collection/[\w-]+/)"')
_POSTCODE = re.compile(r"\b(75\d{3})\b")
# Guide headings that are no room: the article's own sections.
_NOT_A_ROOM = re.compile(
    r"^(?:paris intra-muros|l'est|le nord|le sud|l'ouest|le retour|selon |une soirée|saint-valentin|demande en mariage|"
    r"week-end sans|une nuit après|le dernier métro|jacuzzi privatif ou|réservez|comparez|croire|rater|réserver|"
    r"ce qui le rend|profitez|rédigé par|épingler|dîner|flâneries|évasion au|moments magiques)",
    re.IGNORECASE,
)


def room_pages(client: httpx.Client) -> Iterator[str]:
    """The room pages of the three catalogues."""
    for url in LOVEROOMERS_SITEMAPS:
        yield from (loc for loc, _ in sitemap(client, url) if _LOVEROOMERS_PARIS.match(loc))
    products = client.get(LOVENSPA_PRODUCTS).json()["products"]
    yield from (f"https://lovenspa.fr/products/{product['handle']}" for product in products)
    yield from dict.fromkeys(_LOVE_IDF_ROOM.findall(client.get(LOVE_IDF_PARIS).text))


def parse_room(url: str, page: str) -> dict[str, Any] | None:
    """A room's facts from its LodgingBusiness, its price from the offer, its booking link from the page."""
    lodging = ld_node(page, "LodgingBusiness")
    if not lodging.get("name"):
        return None
    address = lodging.get("address") or {}
    geo = lodging.get("geo") or {}
    offer = lodging.get("makesOffer") or {}
    product = ld_node(page, "Product")
    offers = product.get("offers") or []
    price = next((o.get("price") for o in (offers if isinstance(offers, list) else [offers]) if o.get("price")), None)
    # Love Île-de-France gives "75003 Paris" as locality and the price as the range.
    locality = address.get("addressLocality") or ""
    range_ = str(lodging.get("priceRange") or "")
    images = lodging.get("image") or product.get("image")
    host = urlsplit(url).netloc.removeprefix("www.")
    # Loveroomers escapes its names twice: "Laz&amp;#039; Hotel".
    name = html.unescape(html.unescape(lodging["name"]))
    booking = None
    if host == "loveroomers.fr" and (link := _LOVEROOMERS_BOOKING.search(page)):
        booking = link.group(1)
    elif host == "lovenspa.fr":
        booking = url
    return {
        "url": url,
        "site": host,
        "name": name,
        "venue_name": name,
        "address": address.get("streetAddress"),
        "postal_code": address.get("postalCode") or (m.group(1) if (m := _POSTCODE.search(locality)) else None),
        "latitude": geo.get("latitude"),
        "longitude": geo.get("longitude"),
        "image_url": images[0] if isinstance(images, list) and images else images if isinstance(images, str) else None,
        "price_min": offer.get("lowPrice") or price or (range_ if range_.isdigit() else None),
        "price_max": offer.get("highPrice"),
        "price_label": "la nuit",
        "booking_url": booking,
        "website": booking or url,
        "amenities": [a.get("name") for a in lodging.get("amenityFeature") or [] if a.get("value")],
        "lead_text": lines(lodging.get("description")),
    }


def guide_rooms(url: str, page: str) -> list[dict[str, Any]]:
    """The rooms a guide lists, one per heading."""
    rooms = []
    for idea in parse_article(url, page):
        if _NOT_A_ROOM.search(idea["name"]):
            continue
        rooms.append(idea | {"url": url, "site": urlsplit(url).netloc.removeprefix("www."), "venue_name": idea["name"]})
    return rooms


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    page = urlsplit(payload.get("article_url") or payload["url"])
    external_id = f"{page.netloc.removeprefix('www.')}{page.path.rstrip('/')}"
    if payload.get("article_url"):
        external_id += f"#{_slug(payload['name'])}"
    return RawRecord(source_id=SOURCE_ID, external_id=external_id, url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    name = html.unescape(payload["name"])  # payloads collected before names were unescaped twice
    facts = payload | {"name": name, "venue_name": name, "tags": ["hôtel"], "evening": True, "per_couple": True}
    return normalize_facts(to_raw_record(payload), facts, payload["site"], now)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for url in room_pages(client):
        for payload in page(client, url, lambda r: complete_place(room) if (room := parse_room(url, r.text)) else None, delay):
            yield normalize(payload, now)
    for url in GUIDES:
        for room in page(client, url, lambda r: [complete_place(room) for room in guide_rooms(url, r.text)], delay):
            yield normalize(room, now)


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
