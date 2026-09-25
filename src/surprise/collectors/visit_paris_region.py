"""Collector for VisitParisRegion (Paris Region tourist board, tier 1: official listings).

Place pages come from the French sitemap (one path segment: "/fr/<slug>"; the
themed routes, practical pages and services are left out). Each page gives the
name, teaser (lead_text), breadcrumb (categories), address block, official
site, map coordinates, opening days, prices and photo. Shops and lodgings are
left out by their breadcrumb.
"""

import re
import time as clock
from datetime import datetime
from typing import Any, Iterator

import httpx

from surprise.collectors.common import Normalized, euro_amounts, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, normalize_facts, sitemap, text, utc_now
from surprise.collectors.paris_zigzag import is_evening
from surprise.models import RawRecord

SOURCE_ID = "visit_paris_region"
BASE_URL = "https://www.visitparisregion.com"
SITEMAP = f"{BASE_URL}/fr/sitemap.xml"
DELAY_SECONDS = 1.0

_PLACE = re.compile(r"^https://www\.visitparisregion\.com/fr/([\w-]+)$")
_NOT_PLACE = re.compile(r"^(?:parcours|en-pratique|services|evenements|a-voir-a-faire|paris-museum-pass)")
_SKIPPED_BREADCRUMB = re.compile(r"shopping|boutique|mode|hébergement|hôtel|dormir|services|transport", re.IGNORECASE)
_TITLE = re.compile(r'<h1 class="crtBanner-title">(.*?)</h1>', re.DOTALL)
_TEASER = re.compile(r'<div class="crtBanner-teaser">(.*?)</div>', re.DOTALL)
_CRUMB = re.compile(r'class="crtBreadcrumb-link(?: [^"]*)?"[^>]*>([^<]+)<')
_ADDRESS = re.compile(r'<address class="crtProductContact-adress">(.*?)</address>', re.DOTALL)
_WEBSITE = re.compile(r'<a href="([^"]+)" class="crtLink crtProductContact-link"')
_COORDINATES = re.compile(r'data-latitude="(-?[\d.]+)"\s+data-longitude="(-?[\d.]+)"')
_OPENING = re.compile(r'class="crtProductOpeningDays">(.*?)(?:Tarifs|</section>)', re.DOTALL)
_PRICES = re.compile(r'class="crtProductPrices">(.*?)(?:Langues parlées|</section>)', re.DOTALL)
_OG_IMAGE = re.compile(r'<meta property="og:image" content="([^"]+)"')


def fetch_place_urls(client: httpx.Client) -> list[str]:
    urls = [loc for loc, _ in sitemap(client, SITEMAP)]
    return list(dict.fromkeys(url for url in urls if (m := _PLACE.match(url)) and not _NOT_PLACE.match(m.group(1))))


def parse_place(url: str, page: str) -> dict[str, Any]:
    title = _TITLE.search(page)
    address = _ADDRESS.search(page)
    coordinates = _COORDINATES.search(page)
    opening = text(_OPENING.search(page).group(1)) if _OPENING.search(page) else ""
    prices = text(_PRICES.search(page).group(1)).removeprefix("Tarifs").strip() if _PRICES.search(page) else ""
    amounts = euro_amounts(prices)
    image = _OG_IMAGE.search(page)
    breadcrumb = [text(crumb) for crumb in _CRUMB.findall(page)]
    return {
        "url": url,
        "slug": url.rsplit("/", 1)[-1],
        "name": text(title.group(1)) if title else None,
        # "Station F / 75013 Paris 13ème"
        "address": text(address.group(1)) if address else None,
        "latitude": coordinates.group(1) if coordinates else None,
        "longitude": coordinates.group(2) if coordinates else None,
        "website": _WEBSITE.search(page).group(1) if _WEBSITE.search(page) else None,
        "evening": is_evening(opening),
        "opening": opening or None,
        "free": prices.lower().startswith("gratuit") and not amounts,
        "price_min": float(amounts[0]) if amounts else None,
        "price_max": float(amounts[-1]) if amounts else None,
        "price_label": prices or None,
        "image_url": image.group(1) if image else None,
        "breadcrumb": breadcrumb,
        "category_text": " ".join(breadcrumb),
        "lead_text": text(_TEASER.search(page).group(1)) if _TEASER.search(page) else None,
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(source_id=SOURCE_ID, external_id=payload["slug"], url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    raw = to_raw_record(payload)
    if _SKIPPED_BREADCRUMB.search(" ".join(payload.get("breadcrumb") or [])):
        return Normalized(raw, rejection="hors sujet")
    return normalize_facts(raw, payload, "VisitParisRegion", now)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for index, url in enumerate(fetch_place_urls(client)):
        if index:
            clock.sleep(delay)
        response = client.get(url)
        if response.status_code == 200:
            yield normalize(parse_place(url, response.text), now)


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
