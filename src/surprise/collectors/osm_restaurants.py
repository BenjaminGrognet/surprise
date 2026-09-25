"""Collector for Paris restaurants bookable online, from OpenStreetMap (tier 1: open data, ODbL).

The restaurants of Paris with a website are listed by the Overpass API (name,
cuisine, address, coordinates, opening hours). Each website is read once: a
restaurant is kept when its site links to or embeds a booking engine (Zenchef,
SevenRooms, TheFork, OpenTable…), directly or on its "Réserver" page, and the
table can then be checked for a date (surprise.availability). The site gives
the photo (og:image) and the description (meta description, lead_text).
Restaurants without online booking are rejected: the directory is exhaustive,
unlike the media's picks, which keep walk-in restaurants.
"""

import html
import re
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import httpx

from surprise.booking import engine_in
from surprise.collectors.common import Normalized, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, complete_place, normalize_facts, utc_now
from surprise.models import RawRecord

SOURCE_ID = "osm_restaurants"
# The main instance is often busy: its public mirrors answer the same query.
OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
OVERPASS_QUERY = """[out:json][timeout:180];
area["ISO3166-2"="FR-75C"]->.paris;
(nwr["amenity"="restaurant"]["name"]["website"](area.paris);
 nwr["amenity"="restaurant"]["name"]["contact:website"](area.paris););
out center tags;"""
USER_AGENT = "surprise-collector/0.1"
# Websites are on as many hosts as restaurants: a few at a time, each host asked once or twice.
WORKERS = 8
BATCH = 16

_META = re.compile(r"<meta\s[^>]*>", re.IGNORECASE)
_ATTRIBUTE = re.compile(r'([\w:-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')')
_URL = re.compile(r"https?://[^\s\"'<>\\)]+")
_ASSET = re.compile(r"\.(?:js|css|png|svg|jpe?g|woff2?)(?:[?#]|$)", re.IGNORECASE)


def fetch_restaurants(client: httpx.Client) -> list[dict[str, Any]]:
    """Named restaurants of Paris with a website, in a stable order."""
    for url in OVERPASS_URLS:
        try:
            response = client.post(url, data={"data": OVERPASS_QUERY}, timeout=240)
            response.raise_for_status()
            break
        except httpx.HTTPError as error:
            failure = error
    else:
        raise failure
    places = [e for e in response.json().get("elements") or [] if _website(e.get("tags") or {})]
    return sorted(places, key=lambda e: (e["type"], e["id"]))


def _website(tags: dict[str, str]) -> str | None:
    site = (tags.get("website") or tags.get("contact:website") or "").split(";")[0].strip()
    if site and not site.startswith("http"):
        site = f"https://{site}"
    return site or None


def read_site(client: httpx.Client, url: str) -> dict[str, Any]:
    """Booking engine, booking link, photo and description of a restaurant's site."""
    from surprise.enrich import booking_link  # the enrichment imports the collectors

    try:
        page = client.get(url)
    except httpx.HTTPError:
        return {"site_error": "injoignable"}
    if page.status_code != 200:
        return {"site_error": f"HTTP {page.status_code}"}
    text, found = page.text, _meta(page.text)
    image = found.get("og:image") or found.get("twitter:image")
    result = {
        "image_url": urljoin(str(page.url), html.unescape(image)) if image else None,
        "lead_text": found.get("og:description") or found.get("description"),
    }
    engine = engine_in(str(page.url)) or engine_in(text)
    link = _engine_link(text)
    if not engine and (reserve := booking_link(str(page.url), text)):
        # The "Réserver" page embeds the widget.
        engine = engine_in(reserve)
        link = reserve if engine else None
        if not engine:
            try:
                linked = client.get(reserve)
            except httpx.HTTPError:
                linked = None
            if linked is not None and linked.status_code == 200:
                engine = engine_in(str(linked.url)) or engine_in(linked.text)
                link = (_engine_link(linked.text) or reserve) if engine else None
    return result | {"engine": engine, "booking_url": link or (str(page.url) if engine else None)}


def _engine_link(page: str) -> str | None:
    """The first booking page of a known engine in the page, not its script or stylesheet."""
    for url in _URL.findall(page):
        url = html.unescape(url).replace("&#038;", "&")
        if engine_in(url) and not _ASSET.search(url):
            return url
    return None


def _meta(page: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for tag in _META.findall(page[:300_000]):
        attributes = {k.lower(): html.unescape(a or b) for k, a, b in _ATTRIBUTE.findall(tag)}
        key = attributes.get("property") or attributes.get("name")
        if key and attributes.get("content"):
            found.setdefault(key.lower(), attributes["content"].strip())
    return found


def facts(place: dict[str, Any], site: dict[str, Any]) -> dict[str, Any]:
    tags = place.get("tags") or {}
    centre = place.get("center") or place
    street = " ".join(filter(None, [tags.get("addr:housenumber"), tags.get("addr:street")]))
    cuisines = [c.strip().replace("_", " ") for c in (tags.get("cuisine") or "").split(";") if c.strip()]
    return {
        "osm_id": f"{place['type']}/{place['id']}",
        "name": tags.get("name"),
        "venue_name": tags.get("name"),
        "address": street or None,
        "postal_code": tags.get("addr:postcode"),
        "latitude": centre.get("lat"),
        "longitude": centre.get("lon"),
        "website": _website(tags),
        "opening_hours": tags.get("opening_hours"),
        "cuisine": cuisines,
        "diet": sorted(k.removeprefix("diet:") for k, v in tags.items() if k.startswith("diet:") and v in ("yes", "only")),
        "outdoor_seating": tags.get("outdoor_seating") == "yes",
        "category_text": " ".join(["restaurant", *cuisines]),
        "tags": cuisines,
        **site,
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(
        source_id=SOURCE_ID,
        external_id=payload["osm_id"],
        url=safe_url(f"https://www.openstreetmap.org/{payload['osm_id']}"),
        payload=payload,
    )


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    raw = to_raw_record(payload)
    if payload.get("site_error"):
        return Normalized(raw, rejection=f"site {payload['site_error']}")
    if not payload.get("engine"):
        return Normalized(raw, rejection="sans réservation en ligne")
    return normalize_facts(raw, complete_place(payload), "OpenStreetMap (ODbL)", now)


def collect(client: httpx.Client, now: datetime | None = None) -> Iterator[Normalized]:
    now = now or utc_now()
    places = fetch_restaurants(client)
    with httpx.Client(timeout=20, follow_redirects=True, headers=BROWSER_HEADERS) as sites, ThreadPoolExecutor(WORKERS) as pool:
        # Batches keep --limit meaningful: the next websites are read only when asked for.
        for start in range(0, len(places), BATCH):
            batch = places[start : start + BATCH]
            read = pool.map(lambda place: read_site(sites, _website(place["tags"])), batch)
            for place, site in zip(batch, read):
                yield normalize(facts(place, site), now)


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
