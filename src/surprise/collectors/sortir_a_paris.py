"""Collector for Sortir à Paris (outings agenda and media, tier 3).

Articles come from the French sitemaps (robots.txt lists them), those modified
within the last 60 days in the sections the catalogue lacks: insolite, soirées,
spectacles (cabarets, cirque, drag), gaming (escape games, réalité virtuelle),
Halloween, bars. Each article ends with a practical block marked up in
schema.org microdata:

    <meta itemprop="startDate" content="2026-09-24T00:00:00+02:00"/>
    <strong>Dates et Horaires</strong><br/> Samedi : de 20h à 3h
    <span itemprop="location" itemtype="http://schema.org/Place">… name, streetAddress, postalCode
    <strong>Tarifs</strong><br/> 25 €
    <strong>Site officiel</strong><br/> <a href="https://…">
    <strong>Réservations</strong><br/> <a href="https://…">

with the coordinates of each place on its map. Articles without a place (news,
video games) are skipped. The first place of the block is kept. The article's
summary (description) is kept for Claude to rewrite a description: to remove
before any public use.
"""

import html
import json
import re
from datetime import datetime, timedelta
from typing import Any, Iterator
from urllib.parse import urlsplit

import httpx

from surprise.collectors.common import Normalized, euro_amounts, page, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, ld_node, normalize_facts, sitemap, text, utc_now
from surprise.collectors.paris_zigzag import PARIS, _clean_url, is_evening
from surprise.models import RawRecord

SOURCE_ID = "sortir_a_paris"
BASE_URL = "https://www.sortiraparis.com"
SITEMAP_INDEX = f"{BASE_URL}/sitemap-index.xml"
SINCE = timedelta(days=60)
DELAY_SECONDS = 1.0

# "<section>/<sub-section>" of the outings the catalogue lacks; articles only, not the guides (lists).
_SECTIONS = {
    "loisirs/insolite", "soiree", "scenes/spectacle", "loisirs/gaming", "actualites/halloween",
    "hotel-restaurant/bar-cafes",
}
_ARTICLE = re.compile(r"^https://www\.sortiraparis\.com/(.+?)/articles/(\d+)-[\w-]+$")
_PRACTICAL = re.compile(r'id="practical-info"(.*?)(?:<div id="map-canvas"|<div class="tags">|$)', re.DOTALL)
_FIELD = re.compile(r"<p[^>]*>\s*<strong>([^<]+)</strong>\s*<br\s*/?>(.*?)</p>", re.DOTALL)
_PLACE = re.compile(r'itemprop="location"[^>]*schema\.org/Place"(.*?)</span>\s*</span>', re.DOTALL)
_ITEMPROP = r'itemprop="{}"[^>]*>([^<]*)<'
_META = r'<meta itemprop="{}" content="([^"]+)"'
_LINK = re.compile(r'<a\s[^>]*href="(https?://[^"]+)"')
_MARKERS = re.compile(r"_mapHandler\.init\((\{.*?\})\);")
_OG_IMAGE = re.compile(r'<meta property="og:image" content="([^"]+)"')
_FREE = re.compile(r"gratuit|entrée libre|accès libre", re.IGNORECASE)
# Free said among other facts: the entry, not the cloakroom.
_FREE_ENTRY = re.compile(r"(?:entrée|accès) (?:libre|gratuite?)", re.IGNORECASE)
_DURATION = re.compile(r"\bdurée\b", re.IGNORECASE)
_SITE_SUFFIX = re.compile(r"\s*[-–|]\s*Sortiraparis(?:\.com)?\s*$", re.IGNORECASE)


def fetch_pages(client: httpx.Client, now: datetime) -> Iterator[str]:
    """Articles of the chosen sections modified since the cutoff, the latest first, sitemap by sitemap."""
    cutoff = (now.astimezone(PARIS).date() - SINCE).isoformat()
    for child, _ in sitemap(client, SITEMAP_INDEX):
        if "/sitemap-fr-" not in child:
            continue
        entries = [(lastmod or "", loc) for loc, lastmod in sitemap(client, child) if (lastmod or "") >= cutoff and _in_scope(loc)]
        for _, loc in sorted(entries, reverse=True):
            yield loc


def parse_article(url: str, page: str) -> dict[str, Any] | None:
    """The facts of an article's practical block, or None for an article about no place."""
    block = _PRACTICAL.search(page)
    place = _PLACE.search(block.group(1)) if block else None
    if not place:
        return None
    practical = block.group(1)
    fields = {text(label).lower(): value for label, value in _FIELD.findall(practical)}
    article = ld_node(page, "NewsArticle")
    title = text(article.get("headline")) or _og_title(page)
    markers = _markers(page)
    prices = text(fields.get("tarifs") or fields.get("tarif") or fields.get("prix") or "")
    # "Plus d'informations", line by line; a duration ("Durée : 1h30") is no opening hour.
    more_lines = [text(line) for line in re.split(r"<br\s*/?>", fields.get("plus d'informations") or "")]
    more = " ".join(line for line in more_lines if line and not _DURATION.search(line))
    amounts = euro_amounts(prices)
    hours = " ".join(filter(None, [text(fields.get("dates et horaires")), more]))
    cover = _OG_IMAGE.search(page)
    article_id = _ARTICLE.match(url)
    return {
        "url": url,
        "article_id": article_id.group(2) if article_id else urlsplit(url).path,
        "section": _section(url),
        "name": title,
        "venue_name": text(_first(_ITEMPROP.format("name"), place.group(1))) or None,
        "address": text(_first(_ITEMPROP.format("streetAddress"), place.group(1))) or None,
        "postal_code": text(_first(_ITEMPROP.format("postalCode"), place.group(1))) or None,
        "latitude": markers[0].get("l") if markers else None,
        "longitude": markers[0].get("L") if markers else None,
        "starts_on": _first(_META.format("startDate"), practical),
        "ends_on": _first(_META.format("endDate"), practical),
        "hours": hours or None,
        "evening": is_evening(hours) if hours else None,
        "price_label": prices or None,
        "price_min": float(amounts[0]) if amounts else None,
        "price_max": float(amounts[-1]) if amounts else None,
        "free": not amounts and bool(_FREE.search(prices) if prices else _FREE_ENTRY.search(more)),
        "website": _link(fields.get("site officiel")),
        "booking_url": _link(fields.get("réservations") or fields.get("réservation") or fields.get("billetterie")),
        "image_url": html.unescape(cover.group(1)) if cover else None,
        "category_text": " ".join([_section(url).replace("/", " "), title]),
        "lead_text": html.unescape(article.get("description") or "") or None,
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(source_id=SOURCE_ID, external_id=payload["article_id"], url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    return normalize_facts(to_raw_record(payload), payload, "Sortir à Paris", now)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for url in fetch_pages(client, now):
        for payload in page(client, url, lambda r: parse_article(url, r.text), delay):
            yield normalize(payload, now)


def _first(pattern: str, fragment: str) -> str | None:
    match = re.search(pattern, fragment)
    return html.unescape(match.group(1)).strip() if match else None


def _link(fragment: str | None) -> str | None:
    """The first real link of a field ("#adresse-invalide" when the site is unknown)."""
    match = _LINK.search(fragment or "")
    return _clean_url(html.unescape(match.group(1))) if match else None


def _markers(page: str) -> list[dict[str, Any]]:
    match = _MARKERS.search(page)
    try:
        return json.loads(match.group(1)).get("markers") or [] if match else []
    except json.JSONDecodeError:
        return []


def _og_title(page: str) -> str:
    match = re.search(r'<meta property="og:title" content="([^"]+)"', page)
    return _SITE_SUFFIX.sub("", text(match.group(1))) if match else ""


def _section(url: str) -> str:
    match = _ARTICLE.match(url)
    return match.group(1) if match else ""


def _in_scope(url: str) -> bool:
    return _section(url) in _SECTIONS


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
