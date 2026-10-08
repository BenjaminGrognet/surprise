"""Shared normalization of the newer collectors, which reduce each record to a flat dict of facts.

A collector reads its source (API, sitemap, JSON embedded in the page, HTML) into:

    name, venue_name, address (street, or the full address line), postal_code,
    latitude, longitude, website, booking_url, image_url, starts_at, ends_at
    (ISO datetimes), starts_on, ends_on (ISO dates), price_min, price_max,
    free (bool), duration_minutes, category_text, tags, audience, lead_text

and `normalize_facts` turns it into an Activity, or a rejection with its reason.
`complete_place` fills a missing postcode from the address text, the
coordinates or the name, on OpenStreetMap (Nominatim, 1 request/s).
"""

import gzip
import html
import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
from pydantic import ValidationError

from surprise.categories import categorize
from surprise.collectors.common import OFF_TOPIC, USER_AGENT, Normalized, join_reasons, safe_url
from surprise.collectors.paris_zigzag import PARIS, WINDOW, postal_code, split_venue
from surprise.models import OUT_OF_AREA, Activity, ActivityKind, Image, Occurrence, Offer, PriceUnit, RawRecord, Venue

# Some sites answer bots with a 429 or a captcha page.
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}
_LD_JSON = re.compile(r"<script[^>]*application/ld(?:\+|&#x2B;)json[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)
_SITEMAP_ENTRY = re.compile(
    r"<(?:url|sitemap)>\s*<loc>\s*(?:<!\[CDATA\[)?([^<\]]+?)(?:\]\]>)?\s*</loc>(?:\s*<lastmod>([^<]+)</lastmod>)?"
)
_TAG = re.compile(r"<[^>]+>")
_BLOCK_BREAK = re.compile(r"<(?:/?p\b|/?h\d|br|/?li|/?div)[^>]*>", re.IGNORECASE)
# "12 rue X, 75011 Paris" in running text.
_ADDRESS_IN_TEXT = re.compile(
    r"\b(\d{1,3}(?:\s?[-/]\s?\d{1,3})?(?:\s?(?:bis|ter))?,?\s+(?:rue|avenue|av\.|boulevard|bd|place|quai|square|passage|"
    r"allée|cour|villa|impasse|parvis|esplanade|pont|jardin|port|cité|galerie|chemin|route)\b[^,.<]{2,60}),?\s*(75\d{3})",
    re.IGNORECASE,
)
_CHILD_AUDIENCE = re.compile(r"\benfants?\b|jeune public|\bkids?\b|anniversaire|en famille|parent[- ]enfant|dès \d an", re.IGNORECASE)
# Not for a couple: meeting other singles, professional events.
_NOT_FOR_COUPLES = re.compile(
    r"célibataires?|celibataires?|speed[- ]?dating|\bsingles?\b|rencontres? amoureuses?|networking|afterwork pro|"
    r"\bsalon (?:de l'emploi|professionnel)|job ?dating|recrutement|formation professionnelle|webinaire|\bwebinar",
    re.IGNORECASE,
)
_osm_client: httpx.Client | None = None


def ld_nodes(page: str) -> list[dict[str, Any]]:
    """The schema.org nodes of a page, @graph flattened."""
    nodes: list[Any] = []
    for block in _LD_JSON.findall(page):
        try:
            data = json.loads(html.unescape(block) if "&quot;" in block else block)
        except json.JSONDecodeError:
            continue
        nodes += data.get("@graph", [data]) if isinstance(data, dict) else data
    return [node for node in nodes if isinstance(node, dict)]


def ld_node(page: str, *types: str) -> dict[str, Any]:
    """The first node of one of these types ("Event" also matches "MusicEvent")."""
    for node in ld_nodes(page):
        node_types = node.get("@type") if isinstance(node.get("@type"), list) else [node.get("@type")]
        if any(isinstance(t, str) and (t in types or any(t.endswith(wanted) for wanted in types)) for t in node_types):
            return node
    return {}


def sitemap(client: httpx.Client, url: str) -> list[tuple[str, str | None]]:
    """(location, lastmod) entries of a sitemap or sitemap index, gzipped or not."""
    response = client.get(url)
    response.raise_for_status()
    content = response.content
    if content[:2] == b"\x1f\x8b":
        content = gzip.decompress(content)
    return [(html.unescape(loc.strip()), lastmod) for loc, lastmod in _SITEMAP_ENTRY.findall(content.decode("utf-8", "replace"))]


def nuxt_data(page: str) -> Any:
    """The state a Nuxt site embeds in its page (__NUXT_DATA__), rebuilt from its flattened form."""
    match = re.search(r'id="__NUXT_DATA__"[^>]*>(.*?)</script>', page, re.DOTALL)
    if not match:
        return None
    values = json.loads(match.group(1))
    built: dict[int, Any] = {}

    def value(index: int) -> Any:
        if not isinstance(index, int) or index < 0:
            return None
        if index in built:
            return built[index]
        item = values[index]
        if isinstance(item, list) and item and isinstance(item[0], str):
            # ["Reactive", 3], ["Date", "2026-…"], ["Set", …]: wrappers around a value.
            result = value(item[1]) if item[0] in ("Reactive", "ShallowReactive", "Ref", "ShallowRef") and len(item) > 1 else item[1:]
        elif isinstance(item, list):
            result = built[index] = []
            result.extend(value(i) for i in item)
        elif isinstance(item, dict):
            result = built[index] = {}
            result.update({key: value(i) for key, i in item.items()})
        else:
            result = item
        built[index] = result
        return result

    return value(0)


def text(fragment: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", fragment or ""))).replace("’", "'").strip()


def lines(fragment: str | None) -> str | None:
    """HTML as plain text, one line per paragraph or list item."""
    parts = (text(part) for part in _BLOCK_BREAK.split(fragment or ""))
    return "\n".join(part for part in parts if part) or None


def address_in_text(value: str | None) -> str | None:
    """The first Paris street address mentioned in a text: '12 rue X, 75011 Paris'."""
    match = _ADDRESS_IN_TEXT.search(value or "")
    return f"{match.group(1).strip()}, {match.group(2)} Paris" if match else None


def ld_address(node: dict[str, Any]) -> dict[str, Any]:
    """Venue facts of a schema.org location (Place with PostalAddress and GeoCoordinates)."""
    location = node.get("location") or node.get("itemReviewed") or {}
    if isinstance(location, list):
        location = next(iter(location), {})
    address = location.get("address") or node.get("address") or {}
    geo = location.get("geo") or node.get("geo") or {}
    if isinstance(address, str):
        address = {"streetAddress": address}
    return {
        "venue_name": location.get("name"),
        "address": address.get("streetAddress"),
        "postal_code": address.get("postalCode"),
        "latitude": geo.get("latitude"),
        "longitude": geo.get("longitude"),
    }


def complete_place(payload: dict[str, Any]) -> dict[str, Any]:
    """A payload without Paris postcode: from its address text, else its coordinates, else its name on OpenStreetMap."""
    if payload.get("postal_code") or (payload.get("address") and postal_code(payload["address"])):
        return payload
    if found := postal_code(" ".join(filter(None, [payload.get("venue_name"), payload.get("address_text")]))):
        return payload | {"postal_code": found}
    # Imported here: the enrichment imports the collectors.
    from surprise.enrich import osm_address, osm_place

    global _osm_client
    _osm_client = _osm_client or httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT})
    if payload.get("latitude") and payload.get("longitude"):
        place = osm_address(_osm_client, float(payload["latitude"]), float(payload["longitude"]))
        if place:
            return payload | {
                "address": payload.get("address") or place["osm_address"],
                "postal_code": place["osm_postal_code"],
                "address_origin": place["osm_url"],
            }
        return payload
    name = payload.get("venue_name") or payload.get("name")
    if not name:
        return payload
    place = osm_place(_osm_client, name, None, None)
    if not place or not place["osm_address"]:
        return payload
    return payload | {
        "address": place["osm_address"],
        "postal_code": place["osm_postal_code"],
        "latitude": place["latitude"],
        "longitude": place["longitude"],
        "address_origin": place["osm_url"],
    }


def normalize_facts(raw: RawRecord, facts: dict[str, Any], now: datetime, window: timedelta = WINDOW) -> Normalized:
    """An activity for a couple or a band of friends in Paris intra-muros, or why the record is rejected."""
    name = " ".join((facts.get("name") or "").split())
    if not name:
        return Normalized(raw, rejection="sans nom")
    # Every reason is noted, the fiche still built while it can be: all of them are seen in moderation.
    reasons = []
    context = " ".join(filter(None, [name, facts.get("audience"), " ".join(facts.get("tags") or [])]))
    if _CHILD_AUDIENCE.search(context):
        reasons.append("jeune public")
    if _NOT_FOR_COUPLES.search(context):
        reasons.append("pas pour un couple")
    if OFF_TOPIC.search(name):
        reasons.append("hors sujet")
    address = re.sub(r"[,\s]*\b(?:France|FR)$", "", " ".join((facts.get("address") or "").split()))
    code = facts.get("postal_code") or postal_code(address) or ""
    if not address and not code:
        return Normalized(raw, rejection=join_reasons(*reasons, "sans lieu"))
    venue_name, street = split_venue(address, default_name=facts.get("venue_name") or name) if address else (None, None)
    try:
        venue = Venue(
            name=facts.get("venue_name") or venue_name or name,
            address=street,
            postal_code=str(code).strip(),
            latitude=_float(facts.get("latitude")),
            longitude=_float(facts.get("longitude")),
        )
    except ValidationError:
        return Normalized(raw, rejection=join_reasons(*reasons, OUT_OF_AREA))

    today = now.astimezone(PARIS).date()
    starts_at, ends_at = parse_datetime(facts.get("starts_at")), parse_datetime(facts.get("ends_at"))
    starts_on = _date(facts.get("starts_on")) or (starts_at.astimezone(PARIS).date() if starts_at else None)
    ends_on = _date(facts.get("ends_on")) or (ends_at.astimezone(PARIS).date() if ends_at else None)
    if (ends_on or starts_on) and (ends_on or starts_on) < today:
        reasons.append("passé")
    if starts_on and starts_on > today + window:
        reasons.append("hors fenêtre")
    if ends_on and starts_on and ends_on < starts_on:
        ends_on = None
    evening = starts_at.astimezone(PARIS).hour >= 19 if starts_at and starts_at.time() != datetime.min.time() else facts.get("evening")
    free = bool(facts.get("free")) and not facts.get("price_min")
    low, high = _price(facts.get("price_min")), _price(facts.get("price_max"))
    if low is not None and high is not None and high < low:
        low, high = high, low
    image = facts.get("image_url")
    # Dated sessions (tours, workshops): those of the window.
    sessions = sorted(filter(None, map(parse_datetime, facts.get("sessions") or [])))
    sessions = [s for s in sessions if today <= s.astimezone(PARIS).date() <= today + window]
    if starts_at and starts_at.date() == (ends_at or starts_at).date():
        occurrences = [Occurrence(starts_at=starts_at, ends_at=ends_at if ends_at and ends_at > starts_at else None)]
    else:
        occurrences = [Occurrence(starts_at=session) for session in sessions]
    if sessions and evening is None:
        evening = any(session.astimezone(PARIS).hour >= 19 for session in sessions)
    try:
        activity = Activity(
            title=name,
            kind=ActivityKind.TEMPORARY if starts_on or ends_on else ActivityKind.PERMANENT,
            starts_on=starts_on,
            ends_on=ends_on,
            duration_minutes=facts.get("duration_minutes") or None,
            website=safe_url(facts.get("website")),
            image=Image(url=image, source_url=raw.url) if safe_url(image) else None,
            is_evening=evening,
            venue=venue,
            categories=categorize(" ".join(filter(None, [name, facts.get("category_text")])), venue.name, facts.get("tags")),
            occurrences=occurrences,
            offers=[
                Offer(
                    label=(facts.get("price_label") or "")[:200] or None,
                    is_free=free,
                    price_min=None if free else low,
                    price_max=None if free else (high if high and high != low else None),
                    price_unit=PriceUnit.PER_COUPLE if facts.get("per_couple") else PriceUnit.PER_PERSON,
                    booking_url=safe_url(facts.get("booking_url")),
                    online_booking=True if facts.get("booking_url") else None,
                    paid_booking=True if facts.get("booking_url") and not free else None,
                )
            ],
            players_min=facts.get("players_min") or None,
            players_max=facts.get("players_max") or None,
        )
    except ValidationError as error:
        return Normalized(raw, rejection=join_reasons(*reasons, f"invalide : {error}"))
    return Normalized(raw, activity=activity, rejection=join_reasons(*reasons))


def _float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _price(value: Any) -> float | None:
    number = _float(str(value).replace(",", ".")) if value not in (None, "") else None
    return number if number is not None and number >= 0 else None


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=PARIS)


def _date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
