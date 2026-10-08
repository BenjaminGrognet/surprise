"""Collector for Time Out Paris (curation media, tier 3).

Pages come from the sitemaps (robots.txt lists them), in the outing sections:
all the reviews of places (bars, restaurants, museums…), the other ones (art,
music, clubbing…) modified within the last 60 days.
A page reviewing one place or event carries a schema.org Review whose
itemReviewed gives the facts: name, address, coordinates, dates, photo. Its
verdict (reviewBody) is kept as lead_text. List articles have no Review and
are skipped.
"""

import re
from datetime import datetime, timedelta
from typing import Any, Iterator

import httpx

from surprise.collectors.common import Normalized, page, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, ld_address, ld_node, normalize_facts, sitemap, utc_now
from surprise.collectors.paris_zigzag import PARIS
from surprise.models import RawRecord

SOURCE_ID = "time_out"
# Pages read less than this many days ago are not read again: venues, which rarely change.
FRESH_DAYS = 30
BASE_URL = "https://www.timeout.fr/paris"
SITEMAP_INDEX = f"{BASE_URL}/sitemap.xml.gz"
SINCE = timedelta(days=60)
DELAY_SECONDS = 1.0

_SECTIONS = {
    "bars", "bar", "restaurants", "restaurant", "art", "musique", "musees", "theatre", "clubbing", "que-faire",
    "que-faire-a-paris", "sites-et-monuments", "cinema", "danse", "terrasse", "boire-et-manger", "humour",
}
# Reviews of places that last: read however old (a restaurant reviewed a year ago is still open), once a month.
# The other sections review events, over once the review is old.
_PLACES = {"bars", "bar", "restaurants", "restaurant", "boire-et-manger", "terrasse", "sites-et-monuments", "musees"}


def fetch_pages(client: httpx.Client, now: datetime) -> Iterator[str]:
    """Pages of the outing sections, the latest first, sitemap by sitemap: all the places, the events modified since the cutoff."""
    cutoff = (now.astimezone(PARIS).date() - SINCE).isoformat()
    for child, _ in sitemap(client, SITEMAP_INDEX):
        entries = [
            (lastmod or "", loc)
            for loc, lastmod in sitemap(client, child)
            if _in_scope(loc) and (_section(loc) in _PLACES or (lastmod or "") >= cutoff)
        ]
        for _, loc in sorted(entries, reverse=True):
            yield loc


def parse_review(url: str, page: str) -> dict[str, Any] | None:
    review = ld_node(page, "Review")
    item = review.get("itemReviewed") or {}
    if not item:
        return None
    image = item.get("image") or review.get("image")
    return ld_address({"location": item}) | {
        "url": url,
        "name": item.get("name") or review.get("headline"),
        "venue_name": item.get("name") if not str(item.get("@type", "")).endswith("Event") else None,
        "starts_on": item.get("startDate"),
        "ends_on": item.get("endDate"),
        "category_text": " ".join(filter(None, [item.get("@type"), _section(url), " ".join(review.get("keywords") or [])])),
        "image_url": image[0] if isinstance(image, list) else image,
        "website": item.get("url") or item.get("sameAs"),
        "rating": (review.get("reviewRating") or {}).get("ratingValue"),
        "lead_text": "\n".join(filter(None, [review.get("headline"), review.get("reviewBody")])) or None,
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    path = payload["url"].removeprefix(BASE_URL).strip("/")
    return RawRecord(source_id=SOURCE_ID, external_id=path, url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    # Time Out names the place in its headline ("Le Royaume de Saba, jardin d'Aden…"): the name comes first.
    # Its page title may follow: "Volver | Restaurants à Roquette".
    name = re.split(r",| \| ", payload.get("name") or "")[0].strip()
    facts = payload | {"name": name, "venue_name": name if payload.get("venue_name") else None}
    return normalize_facts(to_raw_record(payload), facts, now)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for url in fetch_pages(client, now):
        for payload in page(client, url, lambda r: parse_review(url, r.text), delay):
            yield normalize(payload, now)


def _section(url: str) -> str:
    return url.removeprefix(BASE_URL + "/").split("/")[0]


def _in_scope(url: str) -> bool:
    return url.startswith(BASE_URL + "/") and _section(url) in _SECTIONS and url.count("/") >= 5


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
