"""Collector for Paris Secret (curation media, tier 3).

Articles are discovered through the post sitemaps (robots.txt allows crawling).
Two kinds of blocks are read in the article body:

- the Fever cards ("fever-plan"): name, venue, address, next date, price, photo
  and booking link, one activity per card (a card shown in several articles is
  collected once);
- the practical paragraphs, as on Paris ZigZag:

    <strong>Date</strong> : Vendredi 14 mai 2027<br>
    <strong>Lieu</strong> : Zénith Paris – La Villette, 211 avenue Jean Jaurès, 75019 Paris

  named after the heading above them, else the article title.

For this personal prototype the article text about each block (lead_text) and
the photos are kept, for Claude to rewrite a description: to remove before any
public use.
"""

import html
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterator
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from surprise.categories import categorize
from surprise.collectors.common import OFF_TOPIC, Normalized, euro_amounts, page, run, safe_url
from surprise.collectors.paris_zigzag import (
    PARIS,
    WINDOW,
    _fields,
    _labelled,
    _slug,
    is_evening,
    parse_dates,
    postal_code,
    split_venue,
)
from surprise.models import OUT_OF_AREA, Activity, ActivityKind, Image, Occurrence, Offer, RawRecord, Venue

SOURCE_ID = "paris_secret"
BASE_URL = "https://parissecret.com"
SITEMAP_INDEX = f"{BASE_URL}/sitemap_index.xml"
USER_AGENT = "surprise-collector/0.1"
# Articles modified within this period are (re)read.
SINCE = timedelta(days=60)
DELAY_SECONDS = 1.0

_SITEMAP_ENTRY = re.compile(r"<(?:url|sitemap)>\s*<loc>([^<]+)</loc>\s*(?:<lastmod>([^<]+)</lastmod>)?")
_BODY = re.compile(r"<article\b.*?</article>", re.DOTALL)
_TITLE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL)
_PLAN = re.compile(r'<div class="fever-plan full-view"(.*?)<div class="fever-plan__cta"', re.DOTALL)
_PLAN_DATA = re.compile(r'data-fever-plan-([a-z]+)="([^"]*)"')
_PLAN_VENUE = re.compile(r'class="fever-plan__location-link"[^>]*>(.*?)</a>', re.DOTALL)
_OG_IMAGE = re.compile(r'<meta property="og:image" content="([^"]+)"')
_PLAN_IMAGE = re.compile(r'<img[^>]*src="([^"]+)"')
_BLOCK = re.compile(r"<(p|h2|h3)(?:\s[^>]*)?>(.*?)</\1>", re.DOTALL)
_BREAK = re.compile(r"<br[^>]*>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_CHILD_AUDIENCE = re.compile(r"jeune public|pour enfants|en famille", re.IGNORECASE)
_FREE = re.compile(r"gratuit|entrée libre|accès libre", re.IGNORECASE)
# Headings that introduce a block without naming it.
_GENERIC_HEADING = re.compile(r"^(?:infos?|informations?)(?: pratiques?)?$|^(?:où|quand|comment)\b", re.IGNORECASE)
# Paragraphs of the Fever cards, not the article's.
_CARD_TEXT = re.compile(r"davantage de dates disponibles|^Détails de l")


def fetch_articles(client: httpx.Client, today: date, since: timedelta = SINCE) -> list[str]:
    """Articles of the post sitemaps modified since the cutoff, the latest first."""
    cutoff = (today - since).isoformat()
    sitemaps = [loc for loc, lastmod in _entries(client, SITEMAP_INDEX) if "/posts_v2-sitemap" in loc and (lastmod or "") >= cutoff]
    articles = [(lastmod, loc) for sitemap in sitemaps for loc, lastmod in _entries(client, sitemap) if (lastmod or "") >= cutoff]
    return [loc for _, loc in sorted(articles, reverse=True)]


def parse_article(url: str, page: str) -> list[dict[str, Any]]:
    """Fever cards and practical paragraphs of an article, with the article text above each."""
    body_match = _BODY.search(page)
    if not body_match:
        return []
    body = body_match.group(0)
    title = _text(_TITLE.search(body).group(1)) if _TITLE.search(body) else ""
    cover = _OG_IMAGE.search(page)
    base = {"article_url": url, "article_title": title}
    plans = [(m.start(), m.end(), m.group(1)) for m in _PLAN.finditer(body)]
    in_plan = lambda position: any(start <= position < end for start, end, _ in plans)  # noqa: E731

    blocks: list[tuple[int, dict[str, Any]]] = []
    prose: list[tuple[int, str]] = []
    heading = None
    for match in _BLOCK.finditer(body):
        if in_plan(match.start()):
            continue
        tag, inner = match.group(1), match.group(2)
        text = _text(inner)
        if tag in ("h2", "h3"):
            heading = text
            continue
        lines = [_text(line) for line in _BREAK.split(inner)]
        labelled = [_labelled(line) for line in lines if line]
        if any(line["label"] for line in labelled) and any(postal_code(line["text"] or "") for line in labelled):
            name = heading if heading and not _GENERIC_HEADING.search(heading) else title.split(" : ")[0]
            # The article's cover photo: the practical block has none of its own.
            image = html.unescape(cover.group(1)) if cover else None
            blocks.append((match.start(), base | {"kind": "practical", "name": name.strip(" .:"), "lines": labelled, "image_url": image}))
        elif text and not _CARD_TEXT.search(text):
            prose.append((match.start(), text))
    for start, _, plan in plans:
        data = {key: html.unescape(value) for key, value in _PLAN_DATA.findall(plan)}
        venue = _PLAN_VENUE.search(plan)
        image = _PLAN_IMAGE.search(plan)
        blocks.append(
            (
                start,
                base
                | {
                    "kind": "fever_plan",
                    "plan_id": data.get("id"),
                    "name": data.get("name", "").strip(),
                    "venue_name": _text(venue.group(1)) if venue else None,
                    "address": data.get("brand"),
                    "starts_at": data.get("date"),
                    "price": data.get("price"),
                    "image_url": html.unescape(image.group(1)) if image else None,
                    "booking_url": f"https://feverup.com/m/{data.get('id')}",
                },
            )
        )
    blocks.sort(key=lambda block: block[0])
    # Each block gets the article text since the previous one.
    previous = 0
    for position, payload in blocks:
        payload["lead_text"] = "\n".join(text for start, text in prose if previous <= start < position) or None
        previous = position
    return [payload for _, payload in blocks]


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    if payload["kind"] == "fever_plan":
        # A card shown in several articles is one activity.
        external_id = f"fever-{payload['plan_id']}"
    else:
        external_id = f"{urlsplit(payload['article_url']).path.strip('/')}#{_slug(payload['name'])}"
    return RawRecord(source_id=SOURCE_ID, external_id=external_id, url=safe_url(payload["article_url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime, window: timedelta = WINDOW) -> Normalized:
    raw = to_raw_record(payload)
    name = payload["name"]
    if not name:
        return Normalized(raw, rejection="sans nom")
    today = now.astimezone(PARIS).date()
    if payload["kind"] == "fever_plan":
        address, venue_name, dates_text, price_text = payload.get("address") or "", payload.get("venue_name"), None, None
        starts_at = datetime.fromisoformat(payload["starts_at"]).replace(tzinfo=PARIS) if payload.get("starts_at") else None
        starts_on, ends_on = (starts_at.date(), None) if starts_at else (None, None)
        evening = starts_at.hour >= 19 if starts_at else None
        amounts = euro_amounts(f"{payload['price']} €") if payload.get("price") else []
        booking_url = payload.get("booking_url")
    else:
        fields = _fields(payload["lines"])
        address, venue_name = fields.get("address") or "", None
        dates_text, price_text = fields.get("dates"), fields.get("price")
        starts_at = None
        starts_on, ends_on = parse_dates(dates_text, today)
        evening = is_evening(" ".join(filter(None, [dates_text, fields.get("hours")])))
        amounts = euro_amounts(price_text)
        booking_url = None
    if _CHILD_AUDIENCE.search(f"{name} {payload.get('article_title')}"):
        return Normalized(raw, rejection="jeune public")
    if OFF_TOPIC.search(name):
        return Normalized(raw, rejection="hors sujet")
    if not address:
        return Normalized(raw, rejection="sans lieu")
    parsed_name, street = split_venue(address, default_name=venue_name or name)
    try:
        venue = Venue(name=venue_name or parsed_name, address=street, postal_code=postal_code(address) or "")
    except ValidationError:
        return Normalized(raw, rejection=OUT_OF_AREA)
    if (ends_on or starts_on) and (ends_on or starts_on) < today:
        return Normalized(raw, rejection="passé")
    if starts_on and starts_on > today + window:
        return Normalized(raw, rejection="hors fenêtre")
    is_free = bool(price_text and _FREE.search(price_text)) and not any(amounts)
    try:
        activity = Activity(
            title=name,
            kind=ActivityKind.TEMPORARY if starts_on or ends_on else ActivityKind.PERMANENT,
            starts_on=starts_on,
            ends_on=ends_on,
            image=Image(url=payload["image_url"], license="Paris Secret", source_url=raw.url) if payload.get("image_url") else None,
            is_evening=evening,
            venue=venue,
            categories=categorize(name, venue.name),
            occurrences=[Occurrence(starts_at=starts_at)] if starts_at else [],
            offers=[
                Offer(
                    label=price_text[:200] if price_text else None,
                    is_free=is_free,
                    price_min=amounts[0] if amounts and not is_free else None,
                    price_max=amounts[-1] if amounts and not is_free else None,
                    booking_url=safe_url(booking_url),
                    online_booking=True if booking_url else None,
                )
            ],
        )
    except ValidationError as error:
        return Normalized(raw, rejection=f"invalide : {error}")
    return Normalized(raw, activity=activity)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or datetime.now(timezone.utc)
    seen: set[str] = set()
    for url in fetch_articles(client, now.astimezone(PARIS).date()):
        for payload in page(client, url, lambda r: parse_article(url, r.text), delay):
            result = normalize(payload, now)
            if result.raw.external_id not in seen:
                seen.add(result.raw.external_id)
                yield result


def _entries(client: httpx.Client, url: str) -> list[tuple[str, str | None]]:
    response = client.get(url)
    response.raise_for_status()
    return [(html.unescape(loc.strip()), lastmod) for loc, lastmod in _SITEMAP_ENTRY.findall(response.text)]


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub("", fragment))).replace("’", "'").strip()


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
