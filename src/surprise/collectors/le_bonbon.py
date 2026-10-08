"""Collector for Le Bonbon Paris (curation media, tier 3).

Articles come from the sitemaps updated within the last 60 days, in their
order (the latest first; articles carry no lastmod), outings sections only, 150 at
most. Like Paris ZigZag, an article ends each
place or event with a practical block, one fact per line:

    <strong>Fête des Puces</strong><br />
    <strong>Marché aux Puces de Saint-Ouen</strong><br />
    <strong>124, rue des Rosiers – Saint-Ouen-sur-Seine</strong><br />
    <strong>Jeudi 24 septembre 2026 à partir de 19h</strong><br />
    <strong>Gratuit sur invitation</strong><br />
    <a href="https://official.example">Plus d'infos</a>

read with the Paris ZigZag parser. The article text and cover photo are kept:
the description is drawn from the text (or written by Claude).
"""

import itertools
import re
from datetime import datetime, timedelta
from typing import Any, Iterator
from urllib.parse import urlsplit

import httpx

from surprise.collectors.common import Normalized, euro_amounts, page, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, normalize_facts, sitemap, utc_now
from surprise.collectors.paris_zigzag import PARIS, _fields, _slug, booking_link, is_evening, parse_article, parse_dates
from surprise.models import RawRecord

SOURCE_ID = "le_bonbon"
BASE_URL = "https://www.lebonbon.fr"
SITEMAP_INDEX = f"{BASE_URL}/sitemap.xml"
SINCE = timedelta(days=60)
DELAY_SECONDS = 1.0

# Outing sections; news, horoscope, travel and society are left out.
_SECTIONS = {
    "bons-plans", "loisirs", "sorties", "soirees", "festivals-et-concerts", "les-tops-spots", "les-tops", "pepites",
    "food-et-drink", "restaurants", "bars", "expos", "les-tops-culture", "culture", "news-nuit", "nuit",
}
_ARTICLE = re.compile(r"<article.*?</article>", re.DOTALL)
_OG_IMAGE = re.compile(r'<meta property="og:image" content="([^"]+)"')
_FREE = re.compile(r"gratuit|entrée libre|accès libre", re.IGNORECASE)
_DISTRICT = re.compile(r"(\s(?:[–—-]|&[nm]dash;))\s*(\d{1,2}(?:e|er|ème))(?=\s*(?:</strong>)?\s*<br)", re.IGNORECASE)
# Articles read at most, most carry no practical block.
MAX_ARTICLES = 150


def fetch_articles(client: httpx.Client, now: datetime) -> Iterator[str]:
    cutoff = (now.astimezone(PARIS).date() - SINCE).isoformat()
    for child, lastmod in sitemap(client, SITEMAP_INDEX):
        if (lastmod or "") < cutoff:
            continue
        for loc, _ in sitemap(client, child):
            if _is_article(loc):
                yield loc


def parse_blocks(url: str, page: str) -> list[dict[str, Any]]:
    article = _ARTICLE.search(page)
    cover = _OG_IMAGE.search(page)
    # "19 rue de Vaugirard – 6e": the arrondissement alone stands for Paris.
    body = _DISTRICT.sub(r"\1 Paris \2", article.group(0) if article else "")
    blocks = parse_article(url, body)
    for block in blocks:
        block["image_url"] = cover.group(1) if cover else None
    return blocks


def facts(block: dict[str, Any], now: datetime) -> dict[str, Any]:
    fields = _fields(block["lines"])
    starts_on, ends_on = parse_dates(fields.get("dates"), now.astimezone(PARIS).date())
    price = fields.get("price")
    amounts = euro_amounts(price)
    return {
        "name": block["name"],
        "address": fields.get("address"),
        "website": block.get("website"),
        "booking_url": booking_link(block),
        "starts_on": starts_on.isoformat() if starts_on else None,
        "ends_on": ends_on.isoformat() if ends_on else None,
        "evening": is_evening(" ".join(filter(None, [fields.get("dates"), fields.get("hours")]))),
        "free": bool(price and _FREE.search(price)) and not any(amounts),
        "price_min": amounts[0] if amounts else None,
        "price_max": amounts[-1] if amounts else None,
        "price_label": price,
        "image_url": block.get("image_url"),
        "category_text": _section(block["article_url"]),
    }


def to_raw_record(block: dict[str, Any]) -> RawRecord:
    path = urlsplit(block["article_url"]).path.strip("/")
    return RawRecord(source_id=SOURCE_ID, external_id=f"{path}#{_slug(block['name'])}", url=safe_url(block["article_url"]), payload=block)


def normalize(block: dict[str, Any], now: datetime) -> Normalized:
    return normalize_facts(to_raw_record(block), facts(block, now), now)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for url in itertools.islice(fetch_articles(client, now), MAX_ARTICLES):
        for block in page(client, url, lambda r: parse_blocks(url, r.text), delay):
            yield normalize(block, now)


def _section(url: str) -> str:
    parts = urlsplit(url).path.strip("/").split("/")
    return parts[1] if len(parts) > 1 else ""


def _is_article(url: str) -> bool:
    parts = urlsplit(url).path.strip("/").split("/")
    # "/paris/<section>/<slug>/": a slug of several words, not a sub-section.
    return len(parts) == 3 and parts[0] == "paris" and parts[1] in _SECTIONS and parts[2].count("-") >= 3


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
