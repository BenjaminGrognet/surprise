"""Collector for Paris-Friendly (curation media of "bons plans", tier 3).

Pages have sequential ids: the RSS feed gives the latest one and the collector
walks down from it. Only the practical block is read (dates and hours, price,
venue and its link, booking link), plus the title, the og:image and, for this
personal prototype, the article text (lead_text, for Claude to rewrite; to remove
before any public use). Pages without a venue in Paris (products, trips) are rejected.
"""

import html
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

import httpx
from pydantic import ValidationError

from surprise.categories import categorize
from surprise.collectors.common import OFF_TOPIC, Normalized, euro_amounts, page, run, safe_url
from surprise.collectors.paris_zigzag import PARIS, WINDOW, is_evening, parse_dates, postal_code, split_venue
from surprise.models import OUT_OF_AREA, Activity, ActivityKind, Image, Offer, RawRecord, Venue

SOURCE_ID = "paris_friendly"
BASE_URL = "https://www.paris-friendly.fr"
RSS_URL = f"{BASE_URL}/flux-rss-les-bons-plans.xml"
PAGE_URL = f"{BASE_URL}/bon_plan_paris_detaille.php?id={{}}"
USER_AGENT = "surprise-collector/0.1"
DELAY_SECONDS = 1.0
# Pages read at most, from the latest one down.
MAX_PAGES = 500

_RSS_ID = re.compile(r"bon_plan_paris_detaille\.php\?id=(\d+)")
_META = re.compile(r'<meta property="og:(title|image)" content="([^"]*)"')
_INFO = re.compile(r'<li>\s*<div class="icon">\s*<img[^>]*alt="([^"]*)">\s*</div>(.*?)</li>', re.DOTALL)
_ITEMPROP = re.compile(r'<span itemprop="(name|address)">(.*?)</span>', re.DOTALL)
# The article, right after the date block.
_BODY = re.compile(r'itemprop="startDate".*?<div class="content">(.*?)</div>', re.DOTALL)
_BLOCK_BREAK = re.compile(r"<(?:/?p\b|/?h\d|br)[^>]*>", re.IGNORECASE)
_HREF = re.compile(r'href="(https?://[^"]+)"')
_LABEL = re.compile(r"^.*?\s:\s")
_TAG = re.compile(r"<[^>]+>")
_CHILD_AUDIENCE = re.compile(r"jeune public|pour enfants|en famille|\benfants?\b", re.IGNORECASE)
_FREE = re.compile(r"gratuit|entrée libre|^0\s*€", re.IGNORECASE)


def latest_id(client: httpx.Client) -> int:
    response = client.get(RSS_URL)
    response.raise_for_status()
    return max(int(i) for i in _RSS_ID.findall(response.text))


def parse_page(page_id: int, url: str, page: str) -> dict[str, Any]:
    meta = {key: html.unescape(value) for key, value in _META.findall(page)}
    # The practical block is repeated for desktop and mobile: the first occurrence of each is enough.
    infos: dict[str, str] = {}
    for alt, content in _INFO.findall(page):
        infos.setdefault(html.unescape(alt), content)
    place = infos.get("Le lieu", "")
    body = _BODY.search(page)
    # "<strong>chocolat</strong>." → "chocolat."
    paragraphs = [re.sub(r" ([.,])", r"\1", _text(part)) for part in _BLOCK_BREAK.split(body.group(1))] if body else []
    props = {key: _text(value) for key, value in _ITEMPROP.findall(place)}
    return {
        "id": page_id,
        "url": url,
        "title": meta.get("title", ""),
        "image_url": meta.get("image"),
        "lead_text": "\n".join(filter(None, paragraphs)) or None,
        "dates": _value(infos.get("La date")),
        "price": _value(infos.get("Le tarif")),
        "booking": _value(infos.get("Les informations")),
        # "Avec réservation le 24 septembre à 14h : cliquez ici"
        "booking_url": next(iter(_HREF.findall(infos.get("Les informations", ""))), None),
        "venue_name": props.get("name"),
        "address": props.get("address"),
        "website": next((link for link in _HREF.findall(place) if "paris-friendly.fr" not in link), None),
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(source_id=SOURCE_ID, external_id=str(payload["id"]), url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime, window: timedelta = WINDOW) -> Normalized:
    raw = to_raw_record(payload)
    title = payload["title"]
    if not title:
        return Normalized(raw, rejection="sans nom")
    if _CHILD_AUDIENCE.search(title):
        return Normalized(raw, rejection="jeune public")
    if OFF_TOPIC.search(f"{title} {payload['url']}"):
        return Normalized(raw, rejection="hors sujet")
    address = payload.get("address") or ""
    if not address:
        return Normalized(raw, rejection="sans lieu")
    # "28 Rue de Monceau, 75008 Paris 75008 Paris"
    _, street = split_venue(re.sub(r"(\s*75\d{3}\s*Paris)+\s*$", "", address), default_name=title)
    venue_name = payload.get("venue_name") or title
    # A venue named just "Paris" is a placeholder, sometimes with another page's address (lanterns on the lac Daumesnil
    # at the Odéon): kept only when the article itself names the street (Les Éditeurs, "4, carrefour de l'Odéon").
    if venue_name.strip().lower() == "paris":
        if not _street_in_article(street, f"{title} {payload.get('lead_text') or ''}"):
            return Normalized(raw, rejection="lieu imprécis")
        venue_name = title.split(" : ")[0].strip()
    try:
        venue = Venue(name=venue_name, address=street, postal_code=postal_code(address) or "")
    except ValidationError:
        return Normalized(raw, rejection=OUT_OF_AREA)

    today = now.astimezone(PARIS).date()
    # "Les 16, 17 et 18 octobre 2026 - à réserver le 24 septembre à 14h": the booking date is not the event's.
    dates = re.split(r"\s+-\s+", payload.get("dates") or "")[0]
    starts_on, ends_on = parse_dates(dates, today)
    if ends_on and ends_on < today:
        return Normalized(raw, rejection="passé")
    if starts_on and starts_on > today + window:
        return Normalized(raw, rejection="hors fenêtre")

    price_text = payload.get("price") or ""
    amounts = euro_amounts(price_text)
    is_free = bool(_FREE.search(price_text)) and not any(amounts)
    try:
        activity = Activity(
            title=title,
            kind=ActivityKind.TEMPORARY if starts_on or ends_on else ActivityKind.PERMANENT,
            starts_on=starts_on,
            ends_on=ends_on,
            website=safe_url(payload.get("website")),
            image=Image(url=payload["image_url"], license="Paris-Friendly", source_url=raw.url) if payload.get("image_url") else None,
            is_evening=is_evening(dates),
            venue=venue,
            categories=categorize(title, venue.name),
            offers=[
                Offer(
                    label=price_text[:200] or None,
                    is_free=is_free,
                    price_min=amounts[0] if amounts and not is_free else None,
                    price_max=amounts[-1] if amounts and not is_free else None,
                    booking_url=safe_url(payload.get("booking_url")),
                    online_booking=True if payload.get("booking_url") else None,
                )
            ],
        )
    except ValidationError as error:
        return Normalized(raw, rejection=f"invalide : {error}")
    return Normalized(raw, activity=activity)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or datetime.now(timezone.utc)
    latest = latest_id(client)
    for page_id in range(latest, max(latest - MAX_PAGES, 0), -1):
        # Deleted pages redirect to erreur-404.php.
        read = lambda r: parse_page(page_id, str(r.url), r.text) if str(r.url).endswith(".html") else None  # noqa: E731
        for payload in page(client, PAGE_URL.format(page_id), read, delay):
            yield normalize(payload, now)


def _value(fragment: str | None) -> str | None:
    """'<p><strong>Prix</strong> : 12 €</p>' → '12 €'."""
    return _LABEL.sub("", _text(fragment), count=1) or None if fragment else None


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", fragment))).replace("’", "'").strip()


# Street types and abbreviations ("Carr de l'Odéon"), too common to identify a street.
_STREET_TYPES = {"rue", "avenue", "boulevard", "place", "carr", "carrefour", "quai", "passage", "impasse", "allee",
                 "cours", "square", "villa", "chemin", "route", "cite", "parvis", "port", "pont", "galerie", "bis", "ter"}


def _street_in_article(street: str | None, text: str) -> bool:
    """'4 Carr de l'Odéon' is in "Installé au 4, carrefour de l'Odéon…": its name words appear in the text."""
    words = [word for word in re.findall(r"[a-z]{3,}", _fold(street or "")) if word not in _STREET_TYPES | {"des", "les"}]
    folded = _fold(text)
    return bool(words) and all(re.search(rf"\b{word}\b", folded) for word in words)


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text.replace("’", "'")).encode("ascii", "ignore").decode().lower()


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
