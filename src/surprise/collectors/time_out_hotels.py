"""Collector for Time Out Paris hotels (curation media, tier 3): where to spend the night after an evening.

Hotel pages come from the sitemaps (robots.txt lists them), the latest first,
whatever their age: a hotel review stays true for years. Each page reviewing
one hotel carries a schema.org Review whose itemReviewed gives the facts (name,
address, coordinates, photo, official site), the page title (h1) its name;
the room price is in the page ("De 392,50 à 3 280 € la nuit", "à partir de 179 €
la nuitée"), else only its scale ("Prix: €€€", kept in the offer's label). List
articles have no Review and are skipped; hotels outside Paris are rejected.
A hotel is kept only if its site books rooms through a known engine.
"""

import html
import re
from datetime import datetime
from typing import Any, Iterator

import httpx

from surprise.collectors.common import Normalized, page, run, with_reason
from surprise.collectors.facts import BROWSER_HEADERS, normalize_facts, sitemap, utc_now
from surprise.collectors.time_out import BASE_URL, DELAY_SECONDS, SITEMAP_INDEX, parse_review
from surprise.collectors.time_out import to_raw_record as _to_raw_record
from surprise.models import RawRecord

SOURCE_ID = "time_out_hotels"
# Pages read less than this many days ago are not read again: venues, which rarely change.
FRESH_DAYS = 30
_NUMBER = r"(\d[\d\s.]*(?:,\d{1,2})?)"
_NIGHT_RANGE = re.compile(rf"De\s*{_NUMBER}\s*à\s*{_NUMBER}\s*€\s*la nuit", re.IGNORECASE)
_ROOM_PRICE = re.compile(
    rf"(?:Prix de la chambre\s*:\s*(?:autour de|à partir de|dès|entre)?|à partir de|dès|autour de|environ)\s*{_NUMBER}\s*€"
    rf"(?:\s*(?:la|par) (?:nuit|nuitée|chambre))?",
    re.IGNORECASE,
)
_SCALE = re.compile(r'"priceRange"\s*:\s*"(€{1,4})"|Prix: (€{1,4})')
# Time Out marks a hotel that closed in its title: "Sinner Paris (FERMÉ)".
_CLOSED = re.compile(r"\(\s*ferm[ée]e?\s*\)", re.IGNORECASE)
_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
# Without a page title, the headline: "Le Magnifique, la nuit prend des couleurs", "Maison Souquet | Hôtels à Saint-Georges".
_HEADLINE = re.compile(r"\s*(?:,|\||–| - ).*")


def fetch_pages(client: httpx.Client) -> Iterator[str]:
    """Hotel pages, the latest first."""
    entries = [
        (lastmod or "", loc)
        for child, _ in sitemap(client, SITEMAP_INDEX)
        for loc, lastmod in sitemap(client, child)
        if loc.startswith(f"{BASE_URL}/hotels/") and loc.count("/") >= 5
    ]
    for _, loc in sorted(entries, reverse=True):
        yield loc


def parse_hotel(url: str, page: str) -> dict[str, Any] | None:
    payload = parse_review(url, page)
    if not payload:
        return None
    text = html.unescape(page)
    title = html.unescape(_TAG.sub("", h1.group(1))).strip() if (h1 := _H1.search(page)) else None
    low = high = None
    if found := _NIGHT_RANGE.search(text):
        low, high = _amount(found.group(1)), _amount(found.group(2))
    elif found := _ROOM_PRICE.search(text):
        low = _amount(found.group(1))
    scale = next((g for m in _SCALE.finditer(text) for g in m.groups() if g), None)
    label = found.group(0).strip() if found else (f"Prix : {scale}" if scale else None)
    return payload | {"title": title, "price_min": low, "price_max": high, "price_label": label}


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return _to_raw_record(payload).model_copy(update={"source_id": SOURCE_ID})


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    name = payload.get("title") or _HEADLINE.sub("", payload.get("name") or "").strip()
    facts = payload | {
        "name": name,
        "venue_name": name,
        "tags": ["hôtel"],  # the category, whatever the title says
        "evening": True,
        "per_couple": True,  # a room, for the two of them
    }
    closed = "fermé définitivement" if _CLOSED.search(name) else None
    return with_reason(closed, normalize_facts(to_raw_record(payload), facts, "Time Out", now))


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for url in fetch_pages(client):
        for payload in page(client, url, lambda r: parse_hotel(url, r.text), delay):
            yield normalize(payload, now)


def _amount(text: str) -> float | None:
    digits = re.sub(r"[\s.]", "", text).replace(",", ".")
    try:
        return float(digits)
    except ValueError:
        return None


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
