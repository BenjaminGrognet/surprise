"""Collector for selections of outings with friends (Secret Squad: articles, tier 3).

Lists of places where a band of friends goes out in Paris (Paris ZigZag, Topito,
Le Bonbon): activities to share, bars with games, karaoke, bars and festive
restaurants for a birthday. Read like the couple selections (selections_couple):
each h2-h4 heading names a place, the text down to the next one describes it
(lead_text) and may give its address and its
link. An idea linked to a Funbooker listing or to a bar on Privateaser takes its
place from it, else it is located by its name on OpenStreetMap.
"""

from datetime import datetime
from typing import Any, Iterator
from urllib.parse import urlsplit

import httpx

from surprise.collectors.common import Normalized, page, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, complete_place, normalize_facts, utc_now
from surprise.collectors.paris_zigzag import _slug
from surprise.collectors.selections_couple import parse_article, with_listing
from surprise.models import RawRecord

SOURCE_ID = "selections_squad"
# The richest first (addresses, booking links), as --limit reads them in this order.
ARTICLES = [
    "https://topito.com/top-meilleurs-bars-jeux-societe-plateau-paris",
    "https://www.lebonbon.fr/paris/les-tops-food-et-drink/top-des-bars-pour-feter-son-anniversaire/",
    "https://www.pariszigzag.fr/top-redac/activites-entre-amis-paris-ile-de-france/",
    "https://www.lebonbon.fr/paris/les-tops-food-et-drink/bars-a-jeux-paris/",
    "https://www.lebonbon.fr/paris/les-tops-spots/karaoke-a-paris-le-guide-des-meilleurs-lieux/",
    "https://www.lebonbon.fr/paris/les-tops-food-et-drink/5-restos-ou-faire-la-teuf/",
]
DELAY_SECONDS = 1.0


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    article = urlsplit(payload["article_url"])
    external_id = f"{article.netloc.removeprefix('www.')}{article.path.rstrip('/')}#{_slug(payload['name'])}"
    return RawRecord(source_id=SOURCE_ID, external_id=external_id, url=safe_url(payload["article_url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    return normalize_facts(to_raw_record(payload), payload, now)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for url in ARTICLES:
        for idea in page(client, url, lambda r: [complete_place(with_listing(client, i)) for i in parse_article(url, r.text)], delay):
            yield normalize(idea, now)


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
