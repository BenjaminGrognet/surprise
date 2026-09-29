"""Collector for Come to Paris (ticketing marketplace, tier 2: bookable offers).

Product pages come from the sitemap, French version only ("/fre/<category>/<slug>-m<id>"),
once per product. Seasonal categories (New Year, Valentine's Day…) and group or
works council offers are skipped. Each page gives a schema.org Product (name,
prices, photos, short description), the address block, the map coordinates, the
hours and the "Ce qui vous attend" text (lead_text, for Claude to rewrite).
Museum pages that give no address get the place's on OpenStreetMap, by name.
"""

import html
import json
import re
from typing import Any, Iterator

import httpx
from pydantic import ValidationError

from surprise.categories import categorize
from surprise.collectors.common import OFF_TOPIC, Normalized, page, run, safe_url
from surprise.collectors.paris_zigzag import is_evening, postal_code, split_venue
from surprise.enrich import osm_place
from surprise.models import OUT_OF_AREA, Activity, ActivityKind, Image, Offer, RawRecord, Venue

SOURCE_ID = "come_to_paris"
BASE_URL = "https://www.cometoparis.com"
SITEMAP = f"{BASE_URL}/sitemap.xml"
USER_AGENT = "surprise-collector/0.1"
DELAY_SECONDS = 1.0

_PRODUCT = re.compile(r"<loc>(https://www\.cometoparis\.com/fre/([^/<]+)/[^/<]+-m(\d+))</loc>")
# Dated once a year, or not for a couple: groups, works councils, outside Paris.
_SKIPPED_CATEGORIES = re.compile(
    r"nouvel-an|saint-valentin|fete-nationale|noel|fete-des-meres|fete-des-peres|halloween|paques|groupes|^ce$|"
    r"chateaux|disneyland|autour-de-paris|metz|versailles|giverny|normandie|reims|loire",
)
_LD_JSON = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.DOTALL)
_ADDRESS = re.compile(r'<div class="title">Adresse</div>.*?<div class="float_left[^"]*">(.*?)</div>', re.DOTALL)
_MAP = re.compile(r'id="google_map_box" data-latitude="([^"]*)" data-longitude="([^"]*)"')
_HOURS = re.compile(r"<h3>Horaires</h3>(.*?)<h3", re.DOTALL)
# Museum pages give the address only in their summary: "Il est situé au 59-61 Rue de Grenelle, 75007 Paris".
_SUMMARY = re.compile(r'<div class="product_index_summary">(.*?)<ul class="highlights"', re.DOTALL)
_ADDRESS_IN_TEXT = re.compile(
    r"\b(\d{1,3}(?:\s?[-/]\s?\d{1,3})?(?:\s?(?:bis|ter))?,?\s+(?:rue|avenue|av\.|boulevard|bd|place|quai|square|passage|"
    r"allée|cour|villa|impasse|parvis|esplanade|pont|jardin|port)\b[^,.<]{2,60}),?\s*(75\d{3})",
    re.IGNORECASE,
)
_WHAT_TO_EXPECT = re.compile(r'<h2 class="section_title">Ce qui vous attend</h2>(.*?)<h2', re.DOTALL)
_BLOCK_BREAK = re.compile(r"<(?:/?p\b|/?h\d|br|/?li|/?div)[^>]*>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_CHILD_AUDIENCE = re.compile(r"\benfants?\b|kids?\b|anniversaire", re.IGNORECASE)


def fetch_product_urls(client: httpx.Client) -> list[str]:
    """French product pages, one per product, outside the skipped categories."""
    response = client.get(SITEMAP)
    response.raise_for_status()
    urls: dict[str, str] = {}
    for url, category, product_id in _PRODUCT.findall(response.text):
        if not _SKIPPED_CATEGORIES.search(category):
            urls.setdefault(product_id, url)
    return list(urls.values())


def parse_product(url: str, page: str) -> dict[str, Any]:
    """Facts of a product page."""
    # The Product is split in two nodes: offers and photos in one, the name in the other.
    product: dict[str, Any] = {}
    breadcrumb: list[str] = []
    for node in _ld_nodes(page):
        if node.get("@type") == "Product":
            product.update(node)
        elif node.get("@type") == "BreadcrumbList":
            breadcrumb = [html.unescape(item.get("name") or "") for item in node.get("itemListElement") or []]
    offers = product.get("offers") or {}
    images = [image.get("contentUrl") for image in product.get("image") or [] if isinstance(image, dict)]
    address = _ADDRESS.search(page)
    coordinates = _MAP.search(page)
    hours = _HOURS.search(page)
    text = _WHAT_TO_EXPECT.search(page)
    summary = " ".join(_lines(match.group(1))) if (match := _SUMMARY.search(page)) else ""
    if address:
        address_text = ", ".join(_lines(address.group(1)))
    elif in_text := _ADDRESS_IN_TEXT.search(summary):
        address_text = f"{in_text.group(1)}, {in_text.group(2)} Paris"
    else:
        address_text = ""
    return {
        "url": url,
        # Private tours have no Product: the breadcrumb names them.
        "name": html.unescape(product.get("name") or "").strip() or (breadcrumb[-1].strip() if len(breadcrumb) > 1 else ""),
        "low_price": offers.get("lowPrice"),
        "high_price": offers.get("highPrice"),
        # "5 Avenue Albert de Mun<br>75016 Paris"
        "address": address_text,
        "latitude": coordinates.group(1) if coordinates else "",
        "longitude": coordinates.group(2) if coordinates else "",
        "hours": " ".join(_lines(hours.group(1))) if hours else None,
        "categories": breadcrumb[1:-1],
        "image_url": next(iter(images), None),
        "lead_text": ("\n".join(_lines(text.group(1))) if text else summary) or None,
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    product_id = payload["url"].rsplit("-m", 1)[-1]
    return RawRecord(source_id=SOURCE_ID, external_id=product_id, url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any]) -> Normalized:
    raw = to_raw_record(payload)
    title = payload["name"]
    if not title:
        return Normalized(raw, rejection="sans nom")
    if _CHILD_AUDIENCE.search(title):
        return Normalized(raw, rejection="jeune public")
    if OFF_TOPIC.search(title):
        return Normalized(raw, rejection="hors sujet")
    address = payload["address"]
    if not address:
        return Normalized(raw, rejection="sans lieu")
    _, street = split_venue(address, default_name=title)
    try:
        venue = Venue(
            # The product is named after its place ("Aquarium de Paris - Cinéaqua").
            name=title,
            address=street,
            postal_code=postal_code(address) or "",
            latitude=float(payload["latitude"]) if payload["latitude"] else None,
            longitude=float(payload["longitude"]) if payload["longitude"] else None,
        )
    except ValidationError:
        return Normalized(raw, rejection=OUT_OF_AREA)
    low, high = payload.get("low_price"), payload.get("high_price")
    try:
        activity = Activity(
            title=title,
            kind=ActivityKind.PERMANENT,
            website=safe_url(payload["url"]),
            image=Image(url=payload["image_url"], license="Come to Paris", source_url=raw.url) if payload.get("image_url") else None,
            is_evening=is_evening(payload.get("hours") or ""),
            venue=venue,
            categories=categorize(" ".join([title, *payload["categories"]])),
            offers=[
                Offer(
                    price_min=low,
                    price_max=high if high is not None and low is not None and float(high) >= float(low) else None,
                    booking_url=safe_url(payload["url"]),
                    online_booking=True,
                    paid_booking=True,
                )
            ],
        )
    except ValidationError as error:
        return Normalized(raw, rejection=f"invalide : {error}")
    return Normalized(raw, activity=activity)


def collect(client: httpx.Client, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    for url in fetch_product_urls(client):
        for payload in page(client, url, lambda r: with_osm_address(client, parse_product(url, r.text)), delay):
            yield normalize(payload)


def with_osm_address(client: httpx.Client, payload: dict[str, Any]) -> dict[str, Any]:
    """A museum page without address ("Musée Zadkine"): its address on OpenStreetMap, found by name."""
    if payload["address"] or not payload["name"]:
        return payload
    place = osm_place(client, payload["name"], None, None)
    if not place or not place["osm_address"]:
        return payload
    return payload | {
        "address": f"{place['osm_address']}, {place['osm_postal_code']} Paris",
        "latitude": str(place["latitude"]),
        "longitude": str(place["longitude"]),
        "address_origin": place["osm_url"],
    }


def _ld_nodes(page: str) -> list[dict[str, Any]]:
    nodes = []
    for block in _LD_JSON.findall(page):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        nodes += data.get("@graph", [data]) if isinstance(data, dict) else data
    return [node for node in nodes if isinstance(node, dict)]


def _lines(fragment: str) -> list[str]:
    texts = (re.sub(r"\s+", " ", html.unescape(_TAG.sub("", part))).strip() for part in _BLOCK_BREAK.split(fragment))
    return [text for text in texts if text]


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
