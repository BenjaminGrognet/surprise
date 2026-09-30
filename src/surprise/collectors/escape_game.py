"""Collector for EscapeGame.fr (escape games and immersive games directory, tier 2: bookable offers).

Rooms come from the sitemap of rooms (robots.txt lists it), those of Paris by
their address ("/paris/<company>/<room>/"). Escape games, but also action
games, réalité virtuelle, expériences immersives, enquêtes and quiz rooms. The
room page gives its name, its kind, its specs (theme, duration, number of
players, price per player), the company's address with its coordinates, a photo,
the scenario (lead_text) and the booking button, to the company's site, whose
booking engine (Bookeo, 4escape…) is checked like any booking link. A room for
three players or more is not for a couple.
"""

import html
import re
from datetime import datetime
from typing import Any, Iterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from surprise.booking import CLOSED
from surprise.collectors.common import Normalized, euro_amounts, join_reasons, page, run, safe_url, with_reason
from surprise.collectors.facts import BROWSER_HEADERS, complete_place, normalize_facts, sitemap, text, utc_now
from surprise.collectors.paris_zigzag import postal_code
from surprise.models import RawRecord

SOURCE_ID = "escape_game"
# Pages read less than this many days ago are not read again: venues, which rarely change.
FRESH_DAYS = 30
BASE_URL = "https://www.escapegame.fr"
SITEMAP = f"{BASE_URL}/sitemap-room.xml"
DELAY_SECONDS = 1.0

_PARIS_ROOM = re.compile(r"^https://www\.escapegame\.fr/paris/([\w-]+)/([\w-]+)/$")
_NAME = re.compile(r'<h1 itemprop="name">(.*?)</h1>', re.DOTALL)
_KIND = re.compile(r'class="card-activity-type type-[\w-]+">(.*?)<', re.DOTALL)
_SPEC = re.compile(r'<div class="col"><div>\s*([^<]+?)\s*<br\s*/?>(.*?)</div></div>', re.DOTALL)
_ADDRESS = re.compile(r'href="https?://maps\.google\.com/\?ll=(-?[\d.]+),(-?[\d.]+)"[^>]*class="room-address"\s*>(.*?)</a>', re.DOTALL)
_COMPANY = re.compile(r'<strong class="h4 bottom10">(.*?)</strong>', re.DOTALL)
_BOOKING = re.compile(r'id="jsBookingSection">.*?<a href="(https?://[^"]+)"', re.DOTALL)
_HERO = re.compile(r'<img src="([^"]+)"[^>]*itemprop="image"')
_DESCRIPTION = re.compile(r'<meta itemprop="description" content="([^"]*)"')
_MAIN = re.compile(r'id="jsMainColumn"(.*?)id="avis"', re.DOTALL)
_PLAYERS = re.compile(r"(?<!\d)(\d+)\s*(?:à\s*(\d+))?\s*joueurs?", re.IGNORECASE)
_MINUTES = re.compile(r"(?<!\d)(\d+)\s*min", re.IGNORECASE)
_TRACKING = re.compile(r"^(?:utm_\w+|source)$")
# The kind said in the title, for the tags: "Escape game : Crypte".
_KIND_IN_NAME = re.compile(r"escape|game|virtuel|\bvr\b|immersi|enquête|quiz|murder", re.IGNORECASE)


def fetch_rooms(client: httpx.Client) -> list[str]:
    return list(dict.fromkeys(loc for loc, _ in sitemap(client, SITEMAP) if _PARIS_ROOM.match(loc)))


def parse_room(url: str, page: str) -> dict[str, Any] | None:
    name = _NAME.search(page)
    if not name:
        return None
    specs = {text(label).lower(): text(value) for label, value in _SPEC.findall(page)}
    players = _PLAYERS.search(specs.get("nombre de joueurs") or "")
    minutes = _MINUTES.search(specs.get("durée") or "")
    prices = euro_amounts(specs.get("prix"))
    # The company's places: the room is at the first one in Paris.
    places = [(lat, lon, text(address)) for lat, lon, address in _ADDRESS.findall(page)]
    lat, lon, address = next((p for p in places if postal_code(p[2])), places[0] if places else (None, None, None))
    kind = _KIND.search(page)
    booking = _BOOKING.search(page)
    image = _HERO.search(page)
    description = _DESCRIPTION.search(page)
    company = _COMPANY.search(page)
    main = _MAIN.search(page)
    return {
        "url": url,
        "room": "/".join(_PARIS_ROOM.match(url).groups()) if _PARIS_ROOM.match(url) else urlsplit(url).path.strip("/"),
        "room_name": text(name.group(1)),
        "kind": text(kind.group(1)) if kind else None,
        "theme": specs.get("thème"),
        "venue_name": text(company.group(1)) if company else None,
        "address": address,
        "latitude": lat,
        "longitude": lon,
        "players_min": int(players.group(1)) if players else None,
        "players_max": int(players.group(2) or players.group(1)) if players else None,
        "duration_minutes": int(minutes.group(1)) if minutes else None,
        "price_min": float(prices[0]) if prices else None,
        "price_max": float(prices[-1]) if prices else None,
        "price_label": specs.get("prix"),
        "audience": specs.get("âge"),
        "booking_url": _clean(html.unescape(booking.group(1))) if booking else None,
        "image_url": html.unescape(image.group(1)).split("?")[0] if image else None,
        "lead_text": html.unescape(description.group(1)).strip() or None if description else None,
        "closed": bool(main and CLOSED.search(text(main.group(1)))),
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(source_id=SOURCE_ID, external_id=payload["room"], url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    raw = to_raw_record(payload)
    reason = join_reasons(
        "fermé définitivement" if payload.get("closed") else None,
        "pas pour un couple" if (payload.get("players_min") or 2) > 2 else None,
    )
    kind, name = payload.get("kind"), payload["room_name"]
    facts = payload | {
        "name": name if not kind or _KIND_IN_NAME.search(name) else f"{kind} : {name}",
        "website": payload.get("booking_url"),
        "category_text": " ".join(filter(None, [kind, payload.get("theme")])),
        # "dès 12 ans" is no children's show: the age is not the audience.
        "audience": None,
    }
    return with_reason(reason, normalize_facts(raw, facts, "EscapeGame.fr", now))


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for url in fetch_rooms(client):
        # "8 Rue Blondel, Paris": the postcode from the coordinates.
        for payload in page(client, url, lambda r: complete_place(room) if (room := parse_room(url, r.text)) else None, delay):
            yield normalize(payload, now)


def _clean(url: str) -> str:
    """The company's link without the directory's tracking ("?source=escapegamefr&utm_…")."""
    parts = urlsplit(url)
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not _TRACKING.match(k)])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
