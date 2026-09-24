"""Collector for Funbooker (activity marketplace, tier 2: bookable offers).

Listings come from the "other" sitemap, restricted to Paris ones by their URL
("…-a-paris-10eme/voir"). Each page gives a schema.org Product (name, lowest
price), the map block (address, coordinates), the key facts (duration, minimum
age), the breadcrumb (categories), the og:image and the description (lead_text).
"""

import html
import json
import re
import time as clock
from typing import Any, Iterator
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from surprise.categories import categorize
from surprise.collectors.common import OFF_TOPIC, Normalized, run, safe_url
from surprise.collectors.paris_zigzag import postal_code, split_venue
from surprise.models import Activity, ActivityKind, Image, Offer, RawRecord, Venue

SOURCE_ID = "funbooker"
BASE_URL = "https://www.funbooker.com"
SITEMAP = f"{BASE_URL}/listing.other.fr.xml"
USER_AGENT = "surprise-collector/0.1"
DELAY_SECONDS = 1.0

_LOC = re.compile(r"<loc>([^<]+)</loc>")
_PARIS_LISTING = re.compile(r"/fr/annonce/[^/]*-a-paris-\d{1,2}(?:er|eme)(?:-\d+)?/voir$")
_LD_JSON = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.DOTALL)
_MAP = re.compile(r'id="map"[^>]*data-text="([^"]*)"[^>]*data-lat="([^"]*)"[^>]*data-lng="([^"]*)"')
_FACT = re.compile(r'<li class="mr-4[^"]*">\s*<i class="[^"]*\bfa-([\w-]+) fa-lg[^>]*></i>(.*?)</li>', re.DOTALL)
_CRUMB = re.compile(r'<a itemprop="item" href="/fr/category/[^"]*">\s*<span itemprop="name">([^<]*)</span>')
_OG_IMAGE = re.compile(r'<meta property="og:image" content="([^"]+)"')
_DURATION = re.compile(r"(?:(\d+)\s*h\s*(\d{2})?)|(\d+)\s*min", re.IGNORECASE)
_CHILD_AUDIENCE = re.compile(r"\benfants?\b|parent|anniversaire|kids?\b", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_BLOCK_BREAK = re.compile(r"<(?:/?p\b|/?h\d|br|/?li)[^>]*>", re.IGNORECASE)
# "Atelier mochis à Paris 6ème": the arrondissement is shown apart.
_IN_PARIS = re.compile(r"[\s,]*\bà Paris(?:\s+\d{1,2}\s*(?:er|ème|e))?\s*$", re.IGNORECASE)
# The og:image is a 400px square thumbnail: the same Cloudinary image, uncropped and larger.
_THUMBNAIL = re.compile(r"/image/upload/[^/]+/")


def fetch_listing_urls(client: httpx.Client) -> list[str]:
    response = client.get(SITEMAP)
    response.raise_for_status()
    return [url for url in _LOC.findall(response.text) if _PARIS_LISTING.search(url)]


def parse_listing(url: str, page: str) -> dict[str, Any]:
    """Facts of a listing page."""
    product = next((node for node in _ld_nodes(page) if node.get("@type") == "Product"), {})
    address, lat, lng = (html.unescape(v) for v in _MAP.search(page).groups()) if _MAP.search(page) else ("", "", "")
    facts = {icon: _text(text) for icon, text in _FACT.findall(page)}
    image = _OG_IMAGE.search(page)
    return {
        "url": url,
        "name": html.unescape(product.get("name") or ""),
        "low_price": (product.get("offers") or {}).get("lowPrice"),
        "address": address,
        "latitude": lat,
        "longitude": lng,
        "duration": facts.get("clock"),
        "group": facts.get("users"),
        "age": facts.get("child"),
        "categories": [html.unescape(name).strip() for name in _CRUMB.findall(page)],
        "image_url": _THUMBNAIL.sub("/image/upload/f_auto,q_auto,c_limit,w_1200/", html.unescape(image.group(1))) if image else None,
        # The organiser's text, for Claude to rewrite a description.
        "lead_text": "\n".join(filter(None, (_text(part) for part in _BLOCK_BREAK.split(product.get("description") or "")))) or None,
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    slug = urlsplit(payload["url"]).path.strip("/").split("/")[-2]
    return RawRecord(source_id=SOURCE_ID, external_id=slug, url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any]) -> Normalized:
    raw = to_raw_record(payload)
    title = _IN_PARIS.sub("", payload["name"]) or payload["name"]
    if not payload["name"]:
        return Normalized(raw, rejection="sans nom")
    if _CHILD_AUDIENCE.search(payload["name"]):
        return Normalized(raw, rejection="jeune public")
    if OFF_TOPIC.search(payload["name"]):
        return Normalized(raw, rejection="hors sujet")
    # "49 Rue du Faubourg du Temple, 75010 Paris, FR"
    address = re.sub(r",\s*FR$", "", " ".join(payload["address"].split()))
    _, street = split_venue(address, default_name=payload["name"])
    try:
        venue = Venue(
            # Funbooker does not name the place: the activity stands for it.
            name=title,
            address=street,
            postal_code=postal_code(address) or "",
            latitude=float(payload["latitude"]) if payload["latitude"] else None,
            longitude=float(payload["longitude"]) if payload["longitude"] else None,
        )
    except ValidationError:
        return Normalized(raw, rejection="hors Paris intra-muros")
    try:
        activity = Activity(
            title=title,
            kind=ActivityKind.PERMANENT,
            duration_minutes=duration_minutes(payload.get("duration")),
            # The listing page is the activity's page.
            website=safe_url(payload["url"]),
            image=Image(url=payload["image_url"], license="Funbooker", source_url=raw.url) if payload.get("image_url") else None,
            venue=venue,
            # "Activités gastronomiques" are workshops and tastings, never a restaurant.
            categories=[c for c in categorize(" ".join([payload["name"], *payload["categories"]])) if c != "restaurant"],
            offers=[
                Offer(
                    price_min=payload.get("low_price"),
                    booking_url=safe_url(payload["url"]),
                    online_booking=True,
                    paid_booking=True,
                )
            ],
        )
    except ValidationError as error:
        return Normalized(raw, rejection=f"invalide : {error}")
    return Normalized(raw, activity=activity)


def duration_minutes(text: str | None) -> int | None:
    """'2h' → 120, '1h30' → 90, '45 min' → 45."""
    match = _DURATION.search(text or "")
    if not match:
        return None
    hours, minutes, only_minutes = match.groups()
    total = int(only_minutes) if only_minutes else int(hours) * 60 + int(minutes or 0)
    return total or None


def collect(client: httpx.Client, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    for index, url in enumerate(fetch_listing_urls(client)):
        if index:
            clock.sleep(delay)
        response = client.get(url)
        if response.status_code == 200:
            yield normalize(parse_listing(url, response.text))


def _ld_nodes(page: str) -> list[dict[str, Any]]:
    nodes = []
    for block in _LD_JSON.findall(page):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        nodes += data.get("@graph", [data]) if isinstance(data, dict) else data
    return nodes


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub("", fragment))).strip()


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
