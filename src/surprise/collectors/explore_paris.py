"""Collector for Explore Paris (tours of know-how, architecture and hidden places, tier 2: bookable offers).

Tours are listed on the "all tours" pages ("/fr/22-toutes-les-visites?p=N").
Each tour page (PrestaShop) gives its name, price, photo, text (lead_text),
place ("Lieu : Paris"), public transport access and dated sessions. A tour in
Paris is located by its access ("Place de Clichy (métro ligne 13)") on
OpenStreetMap (Nominatim). Most tours are in the Greater Paris suburbs and are left out.
"""

import html
import re
import time as clock
from datetime import datetime
from typing import Any, Iterator

import httpx

from surprise.collectors.common import Normalized, page, run, safe_url, with_reason
from surprise.collectors.facts import BROWSER_HEADERS, USER_AGENT, lines, normalize_facts, text, utc_now
from surprise.collectors.funbooker import duration_minutes
from surprise.collectors.paris_zigzag import _MONTHS, postal_code
from surprise.models import METRO_TOWNS, OUT_OF_AREA, RawRecord

SOURCE_ID = "explore_paris"
BASE_URL = "https://exploreparis.com"
LIST_URL = f"{BASE_URL}/fr/22-toutes-les-visites"
DELAY_SECONDS = 1.0
MAX_PAGES = 40

_TOUR = re.compile(r'href="(https://exploreparis\.com/fr/(\d+)-[\w-]+\.html)"')
_NAME = re.compile(r'<h1 class="product_name" itemprop="name">(.*?)</h1>', re.DOTALL)
_PRICE = re.compile(r'itemprop="price" content="([\d.]+)"')
_OG_IMAGE = re.compile(r'<meta property="og:image" content="([^"]+)"')
_DESCRIPTION = re.compile(r'<div[^>]*id="short_description_content"[^>]*>(.*?)</div>', re.DOTALL)
_FACT = re.compile(r"(Lieu|Durée|Accès en transport en commun|Langue)\s*:\s*(.*?)(?=\s+(?:Lieu|Durée|Accès en transport en commun|Langue)\s*:|\s+-->|$)")
# "Samedi 03 octobre 2026 - 18:00"
_SESSION = re.compile(r"\b(\d{1,2}) (" + "|".join(_MONTHS) + r") (\d{4}) - (\d{1,2}):(\d{2})", re.IGNORECASE)
# "Place de Clichy (métro ligne 13)", "Métro 12, Solferino"
_TRANSPORT = re.compile(r"\((?:métro|rer|bus|tram)[^)]*\)|\b(?:métro|rer|bus|tram|ligne)\s*[\w/]*\s*,?\s*", re.IGNORECASE)


def fetch_tour_urls(client: httpx.Client, delay: float = DELAY_SECONDS) -> Iterator[tuple[str, str]]:
    seen: set[str] = set()
    for number in range(1, MAX_PAGES + 1):
        response = client.get(LIST_URL, params={"p": number} if number > 1 else None)
        if response.status_code != 200:
            return
        new = [(url, tour_id) for url, tour_id in _TOUR.findall(response.text) if tour_id not in seen]
        if not new:
            return
        for url, tour_id in dict.fromkeys(new):
            seen.add(tour_id)
            yield url, tour_id
        clock.sleep(delay)


def parse_tour(url: str, tour_id: str, page: str) -> dict[str, Any]:
    plain = text(page)
    facts = {label: value.strip() for label, value in _FACT.findall(plain[plain.find("Lieu :") :] if "Lieu :" in plain else "")}
    price = _PRICE.search(page)
    image = _OG_IMAGE.search(page)
    sessions = [
        f"{year}-{_MONTHS[month.lower()]:02d}-{int(day):02d}T{int(hour):02d}:{minute}:00+02:00"
        for day, month, year, hour, minute in _SESSION.findall(plain)
    ]
    access = _TRANSPORT.sub(" ", facts.get("Accès en transport en commun") or "").strip(" ,.")
    place = facts.get("Lieu") or ""
    return {
        "url": url,
        "tour_id": tour_id,
        "name": text(html.unescape(_NAME.search(page).group(1))) if _NAME.search(page) else None,
        "city": place,
        "access": access or None,
        "price_min": float(price.group(1)) if price else None,
        "free": bool(price) and float(price.group(1)) == 0,
        "duration_minutes": duration_minutes(facts.get("Durée")),
        "sessions": list(dict.fromkeys(sessions)),
        "image_url": image.group(1) if image else None,
        "category_text": "visite",
        "lead_text": lines(_DESCRIPTION.search(page).group(1)) if _DESCRIPTION.search(page) else None,
        "website": url,
        "booking_url": url,
    }


def locate(client: httpx.Client, payload: dict[str, Any]) -> dict[str, Any]:
    """A tour in Paris: its arrondissement ("Paris- 19ème"), else its meeting area by its access, on OpenStreetMap."""
    city = payload.get("city") or ""
    if not re.match(r"^Paris\b", city):
        return payload
    if code := postal_code(re.sub(r"^Paris\W*(\d{1,2})", r"Paris \1", city)):
        return payload | {"postal_code": code}
    # Imported here: the enrichment imports the collectors.
    from surprise.enrich import osm_area

    # "Arrêt Ella Fitzgerald", "Jacques Bonsergent ou République", "Porte de Bagnolet -"
    access = re.sub(r"^(?:arrêt|station)\s+|\s+ou\s+.*$|\W+$", "", payload.get("access") or "", flags=re.IGNORECASE)
    area = osm_area(client, access) if access else None
    if not area:
        return payload
    return payload | {
        "postal_code": area["osm_postal_code"],
        "latitude": area["latitude"],
        "longitude": area["longitude"],
        "address_origin": area["osm_url"],
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(source_id=SOURCE_ID, external_id=payload["tour_id"], url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    raw = to_raw_record(payload)
    if not re.match(r"^Paris\b", payload.get("city") or "") and (payload.get("city") or "").strip() not in METRO_TOWNS.values():
        return Normalized(raw, rejection=OUT_OF_AREA)
    past = payload.get("sessions") and not any(session[:10] >= now.date().isoformat() for session in payload["sessions"])
    return with_reason("passé" if past else None, normalize_facts(raw, payload, now))


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    with httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT}) as osm_client:
        for url, tour_id in fetch_tour_urls(client, delay):
            for payload in page(client, url, lambda r: locate(osm_client, parse_tour(url, tour_id, r.text)), delay):
                yield normalize(payload, now)


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
