"""Collector for Paris ZigZag (curation media, tier 3: discovery signal only).

Articles are discovered through the sitemaps (robots.txt allows crawling) and
only their practical blocks are read: the name of the place or event, its link
to the official site, venue, address, dates, price and hours, e.g.

    <a href="https://official.example">Name</a><br />
    Venue, 5 rue Example, 75009 Paris<br />
    Du 10 septembre au 31 décembre 2026

The site's terms forbid reusing its content: no editorial text is stored, only
these facts, the article URL as provenance and, for this personal prototype, the
URL of the article photo shown just above the block (to review before any public use). Articles that give
the information only in prose are counted and left for LLM extraction.
"""

import calendar
import html
import re
import time as clock
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from surprise.categories import categorize
from surprise.collectors.common import BOOKING, Normalized, euro_amounts, run, safe_url
from surprise.models import Activity, ActivityKind, Image, Offer, RawRecord, Venue

SOURCE_ID = "paris_zigzag"
BASE_URL = "https://www.pariszigzag.fr"
SITEMAP_INDEX = f"{BASE_URL}/sitemaps.xml"
USER_AGENT = "surprise-collector/0.1"
PARIS = ZoneInfo("Europe/Paris")
WINDOW = timedelta(weeks=6)
# Articles modified within this period are (re)read.
SINCE = timedelta(days=60)
# Pause between two article requests.
DELAY_SECONDS = 1.0

# Other cities, news and family content are out of scope.
_EXCLUDED_SECTIONS = ("famille", "france", "lyon-actu", "lille-actu", "marseille-actu", "bordeaux-actu", "rennes-actu")
_EXCLUDED_SUBSECTIONS = ("paris-au-quotidien/actualites-paris", "paris-au-quotidien/coronavirus")

_SITEMAP_ENTRY = re.compile(r"<(?:url|sitemap)>\s*<loc>([^<]+)</loc>\s*(?:<lastmod>([^<]+)</lastmod>)?")
_PARAGRAPH = re.compile(r"<p(?:\s[^>]*)?>(.*?)</p>", re.DOTALL)
_BREAK = re.compile(r"<br[^>]*>", re.IGNORECASE)
_LINK = re.compile(r"<a\s[^>]*href=\"([^\"]+)\"", re.IGNORECASE)
_ANCHOR = re.compile(r"<a\s[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
# Article photos (WordPress uploads), not the 150x150 thumbnails of related articles.
_IMG = re.compile(r"<img\s[^>]*>", re.IGNORECASE)
_PHOTO_CLASS = re.compile(r"class=\"[^\"]*\bwp-(?:image-\d+|post-image)\b")
_SRC = re.compile(r"\ssrc=\"(https://www\.pariszigzag\.fr/wp-content/uploads/[^\"]+)\"")
_LABEL = re.compile(r"^([A-Za-zÀ-ÿ' ]{2,25}?)\s*:\s*(.*)$")
_POSTAL_CODE = re.compile(r"\b(75\d{3})\b")
_PARIS_DISTRICT = re.compile(r"\bParis\s+(\d{1,2})\s*(?:e|er|ème)\b", re.IGNORECASE)
_STREET = re.compile(
    r"\b\d{1,3}(?:\s?[/-]\s?\d{1,3})?\s?(?:bis|ter)?\s*,?\s+(?:rue|av\.?|avenue|bd|bvd|boulevard|place|quai|passage|impasse|allée|square|"
    r"cité|villa|route|chemin|cour|galerie|carré|port|parvis|esplanade|pont|jardin)\b",
    re.IGNORECASE,
)
_MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
    "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}
_DATE = re.compile(
    r"\b(\d{1,2})(?:er)?(?![\dh:])(?:\s+(" + "|".join(_MONTHS) + r"))?(?:\s+(\d{4}))?", re.IGNORECASE
)
_HAS_MONTH = re.compile(r"\b(" + "|".join(_MONTHS) + r")\b", re.IGNORECASE)
_HOUR = re.compile(r"\b(\d{1,2})\s?h(?:\s?\d{2})?\b", re.IGNORECASE)
# "de 9h à 19h", "18h-2h": the second hour is a closing time.
_HOUR_RANGE = re.compile(r"(?<!\d)(\d{1,2})\s?h?(?:\s?\d{2})?\s*(?:à|-|–)\s*(\d{1,2})\s?h(?:\s?\d{2})?\b", re.IGNORECASE)
# "fin septembre", "début octobre", "mi-novembre": a day of the month.
_MONTH_PART = re.compile(r"\b(fin|début|debut|mi)[\s-]+(" + "|".join(_MONTHS) + r")\b", re.IGNORECASE)
_CHILD_AUDIENCE = re.compile(r"jeune public|pour enfants|en famille", re.IGNORECASE)
_FREE = re.compile(r"gratuit|entrée libre|accès libre", re.IGNORECASE)
_TRACKING_PARAMS = re.compile(r"^(utm_|gclid$|gad_|fbclid$|mc_)")
EVENING_FROM_HOUR = 19
# "fin" is the last day of the month (February: 28).
_MONTH_PART_DAY = {"début": 1, "debut": 1, "mi": 15, "fin": None}

_ADDRESS_LABELS = {"lieu", "adresse", "où", "ou"}
_DATE_LABELS = {"dates", "date", "quand"}
_PRICE_LABELS = {"tarifs", "tarif", "prix", "entrée"}
_HOURS_LABELS = {"horaires", "horaire"}
_KNOWN_LABELS = _ADDRESS_LABELS | _DATE_LABELS | _PRICE_LABELS | _HOURS_LABELS
# A heading above the block, not the name of the place.
_GENERIC_NAME = re.compile(r"^(?:infos?|informations?)(?: pratiques?)?$", re.IGNORECASE)


@dataclass
class Article:
    url: str
    modified: str | None


def fetch_articles(client: httpx.Client, today: date, since: timedelta = SINCE) -> list[Article]:
    """Articles of the post sitemaps modified since the cutoff, outside the excluded sections."""
    cutoff = (today - since).isoformat()
    sitemaps = [loc for loc, lastmod in _entries(client, SITEMAP_INDEX) if "/post-sitemap" in loc and (lastmod or "") >= cutoff]
    articles = []
    for sitemap in sitemaps:
        for loc, lastmod in _entries(client, sitemap):
            if (lastmod or "") >= cutoff and _in_scope(loc):
                articles.append(Article(loc, lastmod))
    return articles


def parse_article(url: str, page: str, modified: str | None = None) -> list[dict[str, Any]]:
    """Practical blocks of an article, as fact-only payloads (one per place or event)."""
    # Booking links anywhere in the article ("réservez ici"), matched to a block by the official site's domain.
    anchors = [(_clean_url(html.unescape(href)), _text(text)) for href, text in _ANCHOR.findall(page)]
    booking_links = [link for link, text in anchors if link and (BOOKING.search(link) or BOOKING.search(text))]
    photos = [
        (tag.start(), src.group(1))
        for tag in _IMG.finditer(page)
        if _PHOTO_CLASS.search(tag.group(0)) and (src := _SRC.search(tag.group(0))) and "-150x150." not in src.group(1)
    ]
    blocks = []
    for match in _PARAGRAPH.finditer(page):
        paragraph = match.group(1)
        if not _BREAK.search(paragraph):
            continue
        raw_lines = _BREAK.split(paragraph)
        lines = [_text(line) for line in raw_lines]
        if not any(_POSTAL_CODE.search(line) or _PARIS_DISTRICT.search(line) for line in lines[1:]):
            continue
        name = lines[0].strip(" .:")
        if not name or len(name) > 120 or _LABEL.match(name):
            continue
        links = [_clean_url(html.unescape(href)) for href in _LINK.findall(paragraph)]
        links = [link for link in links if link and urlsplit(link).netloc not in ("pariszigzag.fr", "www.pariszigzag.fr")]
        first_line_links = [_clean_url(html.unescape(href)) for href in _LINK.findall(raw_lines[0])]
        # The name is usually the link to the official site; otherwise the block's first external link.
        website = next((link for link in first_line_links if link in links), None) or next(iter(links), None)
        domain = _domain(website)
        blocks.append(
            {
                "article_url": url,
                "article_modified": modified,
                "section": "/".join(urlsplit(url).path.strip("/").split("/")[:2]),
                "name": name,
                "website": website,
                "links": links,
                "booking_links": [link for link in booking_links if domain and _domain(link) == domain],
                "lines": [_labelled(line) for line in lines[1:] if line],
                # The last photo above the block: the one of this place in a list article.
                "image_url": next((src for start, src in reversed(photos) if start < match.start()), None),
            }
        )
    return blocks


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    path = urlsplit(payload["article_url"]).path.strip("/")
    return RawRecord(
        source_id=SOURCE_ID,
        external_id=f"{path}#{_slug(payload['name'])}",
        url=safe_url(payload["article_url"]),
        payload=payload,
    )


def normalize(payload: dict[str, Any], now: datetime, window: timedelta = WINDOW) -> Normalized:
    raw = to_raw_record(payload)
    fields = _fields(payload["lines"])
    today = now.astimezone(PARIS).date()

    if _CHILD_AUDIENCE.search(" ".join([payload["name"], *fields.values()])):
        return Normalized(raw, rejection="jeune public")

    address_line = fields.get("address") or ""
    venue_name, street = split_venue(address_line, default_name=payload["name"])
    title = venue_name if _GENERIC_NAME.match(payload["name"]) else payload["name"]
    if _GENERIC_NAME.match(title):
        return Normalized(raw, rejection="sans nom")
    try:
        venue = Venue(name=venue_name, address=street, postal_code=postal_code(address_line) or "")
    except ValidationError:
        return Normalized(raw, rejection="hors Paris intra-muros")

    starts_on, ends_on = parse_dates(fields.get("dates"), today)
    if ends_on and ends_on < today:
        return Normalized(raw, rejection="passé")
    if starts_on and starts_on > today + window:
        return Normalized(raw, rejection="hors fenêtre")

    price_text = fields.get("price")
    amounts = euro_amounts(price_text)
    is_free = bool(price_text and _FREE.search(price_text)) and not any(amounts)
    booking_url = booking_link(payload)
    try:
        activity = Activity(
            title=title,
            # Descriptions are written during enrichment, never taken from the media.
            description=None,
            kind=ActivityKind.TEMPORARY if starts_on or ends_on else ActivityKind.PERMANENT,
            starts_on=starts_on,
            ends_on=ends_on,
            website=safe_url(payload.get("website")),
            image=Image(url=payload["image_url"], license="Paris ZigZag", source_url=raw.url) if payload.get("image_url") else None,
            is_evening=is_evening(" ".join(filter(None, [fields.get("dates"), fields.get("hours")]))),
            venue=venue,
            categories=categorize(title, venue.name, section=payload.get("section")),
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


def booking_link(payload: dict[str, Any]) -> str | None:
    """A ticketing link of the block, the official link if it is one, a booking link to the same site, or another link."""
    website = payload.get("website")
    others = [link for link in payload["links"] if link != website]
    return (
        next((link for link in others if BOOKING.search(link)), None)
        or (website if website and BOOKING.search(website) else None)
        or next(iter(payload.get("booking_links") or []), None)
        or next(iter(others), None)
    )


def postal_code(text: str) -> str | None:
    if match := _POSTAL_CODE.search(text):
        return match.group(1)
    if match := _PARIS_DISTRICT.search(text):
        district = int(match.group(1))
        return f"750{district:02d}" if 1 <= district <= 20 else None
    return None


def split_venue(text: str, default_name: str) -> tuple[str, str | None]:
    """'Théâtre X, 5 rue Y, 75009 Paris' → ('Théâtre X', '5 rue Y'); a bare address keeps the entity name."""
    text = re.sub(r"[\s,.–-]*(?:75\d{3}\s*)?Paris(?:\s+\d{1,2}\s*(?:e|er|ème))?\.?\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*\b75\d{3}\b\s*$", "", text).strip(" ,.–-")
    if match := _STREET.search(text):
        name, street = text[: match.start()].strip(" ,.–-"), text[match.start() :].strip(" ,.–-")
    elif "," in text:
        name, street = (part.strip(" ,.–-") for part in text.split(",", 1))
    else:
        name, street = "", text
    # "La Nouvelle Seine, sur berges, face au 3 quai…"
    name = re.sub(r"[\s,]*\b(?:en )?face (?:au|du|de la)$|[\s,]*\b(?:au|à)$", "", name, flags=re.IGNORECASE)
    return name or default_name, street or None


def parse_dates(text: str | None, today: date) -> tuple[date | None, date | None]:
    """French date phrases: 'Du 25 au 27 septembre 2026', 'Jusqu'au 4 janvier 2027', 'À partir du 10 mai'…"""
    if not text or not _HAS_MONTH.search(text):
        return None, None
    text = _MONTH_PART.sub(lambda m: f"{_MONTH_PART_DAY.get(m.group(1).lower()) or calendar.mdays[_MONTHS[m.group(2).lower()]]} {m.group(2)}", text)
    tokens =[(int(d), m.lower() if m else None, int(y) if y else None) for d, m, y in _DATE.findall(text)]
    # "Du 25 au 27 septembre 2026": a day without month or year takes those of the next date.
    month, year, dates = None, None, []
    for day, token_month, token_year in reversed(tokens):
        month = _MONTHS[token_month] if token_month else month
        year = token_year or year
        if month:
            dates.append((day, month, year, token_year is not None))
    dates.reverse()
    resolved, explicit = [], []
    for day, month, year, has_year in dates:
        try:
            resolved.append(date(year or _nearest_year(day, month, today), month, day))
            explicit.append(has_year)
        except ValueError:
            continue
    if not resolved:
        return None, None
    lowered = text.lower()
    if len(resolved) == 1:
        if "jusqu" in lowered:
            return None, resolved[0]
        if "partir" in lowered or re.search(r"\bdès\b", lowered):
            return resolved[0], None
        return resolved[0], resolved[0]
    starts_on, ends_on = resolved[0], resolved[-1]
    if ends_on < starts_on:
        if not explicit[0] and starts_on.replace(year=starts_on.year - 1) <= ends_on and ends_on >= today:
            # "Du 19 septembre au 27 juin 2027": the season started the year before.
            starts_on = starts_on.replace(year=starts_on.year - 1)
        else:
            # "Du 9 septembre au 16 janvier 2026", a typo for 2027: the season ends the year after.
            ends_on = ends_on.replace(year=ends_on.year + 1)
    return starts_on, ends_on


def is_evening(text: str) -> bool | None:
    """Whether the activity starts in the evening or closes after midnight; "de 9h à 19h" is not."""
    starts = _HOUR_RANGE.sub(lambda m: m.group(0) if int(m.group(2)) < 6 else f"{m.group(1)}h", text)
    hours = [int(h) for h in _HOUR.findall(starts) if int(h) < 24]
    if not hours:
        return None
    # An hour before 6 is a closing time after midnight ("jusqu'à 2h").
    return any(hour >= EVENING_FROM_HOUR or hour < 6 for hour in hours)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or datetime.now(timezone.utc)
    articles = fetch_articles(client, now.astimezone(PARIS).date())
    without_block = 0
    for index, article in enumerate(articles):
        if index:
            clock.sleep(delay)
        response = client.get(article.url)
        if response.status_code != 200:
            continue
        blocks = parse_article(article.url, response.text, article.modified)
        without_block += not blocks
        for payload in blocks:
            yield normalize(payload, now)
    print(f"{len(articles)} articles lus, {without_block} sans bloc pratique (à extraire par LLM)")


def _entries(client: httpx.Client, url: str) -> list[tuple[str, str | None]]:
    response = client.get(url)
    response.raise_for_status()
    return [(html.unescape(loc.strip()), lastmod) for loc, lastmod in _SITEMAP_ENTRY.findall(response.text)]


def _in_scope(url: str) -> bool:
    path = urlsplit(url).path.strip("/")
    return not path.startswith(_EXCLUDED_SECTIONS) and not path.startswith(_EXCLUDED_SUBSECTIONS)


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub("", fragment))).replace("’", "'").strip()


def _labelled(line: str) -> dict[str, str | None]:
    if (match := _LABEL.match(line)) and not _PARIS_DISTRICT.search(match.group(1)):
        label, text = match.group(1).strip(), match.group(2).strip()
        # "Le Gratin : 1 place de Valois, Paris 1er" is a venue, not a label.
        if label.lower() not in _KNOWN_LABELS and postal_code(text):
            return {"label": None, "text": f"{label}, {text}"}
        return {"label": label.lower(), "text": text}
    return {"label": None, "text": line}


def _fields(lines: list[dict[str, str | None]]) -> dict[str, str]:
    """Map block lines to address / dates / price / hours, labelled or recognised by their content."""
    fields: dict[str, str] = {}
    previous: str | None = None
    for line in lines:
        label, text = line["label"], line["text"] or ""
        # A venue name alone on the line before a bare address ("Hippodrome" / "2 route de la Ferme, 75012 Paris").
        if not label and previous and postal_code(text) and _STREET.match(text):
            text = f"{previous}, {text}"
        plain = not label and not postal_code(text) and not _HAS_MONTH.search(text) and not re.search(r"\d", text)
        previous = text if plain else None
        if label in _ADDRESS_LABELS:
            key = "address"
        elif label in _DATE_LABELS:
            key = "dates"
        elif label in _PRICE_LABELS:
            key = "price"
        elif label in _HOURS_LABELS:
            key = "hours"
        elif label:
            continue
        elif postal_code(text):
            key = "address"
        elif _HAS_MONTH.search(text) or "jusqu" in text.lower():
            key = "dates"
        elif "€" in text or re.search(r"\beuros?\b", text, re.IGNORECASE) or _FREE.search(text):
            key = "price"
        else:
            continue
        fields.setdefault(key, text)
    return fields


def _clean_url(url: str) -> str | None:
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        return None
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not _TRACKING_PARAMS.match(k)])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def _domain(url: str | None) -> str | None:
    return urlsplit(url).netloc.removeprefix("www.").lower() if url else None


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:80]


def _nearest_year(day: int, month: int, today: date) -> int:
    """A date without year is the next one to come (a few weeks back still counts as this year)."""
    candidate = date(today.year, month, min(day, 28))
    return today.year if candidate >= today - timedelta(days=60) else today.year + 1


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
