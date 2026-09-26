"""Collector for Paris leisure venues bookable online, from OpenStreetMap (tier 1: open data, ODbL).

Venues of active or unusual outings the media rarely list are found with the
Overpass API: karaoké boxes, axe throwing, laser games, réalité virtuelle and
arcades, bowlings, mini-golfs, trampoline parks, climbing gyms, saunas and
hammams, swimming pools, and bars with darts, billiards or table football.
Escape games are left to the EscapeGame.fr directory (escape_game). Each
website is read as for the restaurants (osm_restaurants): a venue is kept when
its site leads to a booking engine; a bar is kept anyway, walk-in, while open.
The kind is said in the title when the name does not ("Escalade : Arkose").
"""

import re
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

import httpx

from surprise.collectors.common import Normalized, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, complete_place, normalize_facts, utc_now
from surprise.collectors.osm_restaurants import BATCH, USER_AGENT, WORKERS, _website, overpass, read_site
from surprise.models import RawRecord

SOURCE_ID = "osm_loisirs"
OVERPASS_QUERY = """[out:json][timeout:180];
area["ISO3166-2"="FR-75C"]->.paris;
(nwr["leisure"~"^(bowling_alley|miniature_golf|amusement_arcade|trampoline_park|sauna|water_park)$"]["name"](area.paris);
 nwr["amenity"~"^(karaoke_box|public_bath)$"]["name"](area.paris);
 nwr["sport"~"axe_throwing|laser_tag|virtual_reality|climbing|bowling|10pin|9pin|swimming"]["name"](area.paris);
 nwr["amenity"~"^(bar|pub)$"]["sport"~"darts|billiards|shuffleboard"]["name"](area.paris););
out center tags;"""
# Kind of venue, the rarest outings first (--limit reads them in this order):
# key, title word, the name already says it, category words, OSM tags.
KINDS = [
    ("karaoke", "Karaoké", r"karaok", "karaoké", lambda t: t.get("amenity") == "karaoke_box" or "karaoke" in t.get("sport", "")),
    ("axe_throwing", "Lancer de hache", r"hache|\baxe", "lancer de hache", lambda t: "axe_throwing" in t.get("sport", "")),
    ("laser_tag", "Laser game", r"laser", "laser game", lambda t: "laser_tag" in t.get("sport", "")),
    ("virtual_reality", "Réalité virtuelle", r"virtu|\bvr\b", "réalité virtuelle", lambda t: "virtual_reality" in t.get("sport", "")),
    ("amusement_arcade", "Jeu vidéo", r"gaming|jeux? vidéo|réalité virtuelle|\bvr\b", "jeu vidéo arcade", lambda t: t.get("leisure") == "amusement_arcade"),
    ("bowling", "Bowling", r"bowling", "bowling", lambda t: t.get("leisure") == "bowling_alley" or bool({"10pin", "9pin", "bowling"} & _sports(t))),
    ("miniature_golf", "Mini-golf", r"golf", "mini-golf", lambda t: t.get("leisure") == "miniature_golf"),
    ("trampoline", "Trampoline", r"trampo", "trampoline", lambda t: t.get("leisure") == "trampoline_park"),
    ("bar_games", "Bar", r"(?!)", "bar", lambda t: t.get("amenity") in ("bar", "pub") and bool(set(_BAR_GAMES) & _sports(t))),
    ("sauna", "Hammam", r"hammam|sauna|\bspa\b|bains?\b", "hammam sauna", lambda t: t.get("leisure") == "sauna" or t.get("amenity") == "public_bath"),
    ("climbing", "Escalade", r"escalade|grimpe|bloc", "escalade", lambda t: "climbing" in t.get("sport", "")),
    ("swimming", "Piscine", r"piscine|baignade|aqua", "piscine", lambda t: "swimming" in t.get("sport", "") or t.get("leisure") == "water_park"),
]
_CLOSING = re.compile(r"\d{1,2}:\d{2}\s*-\s*(\d{1,2}):\d{2}")
_ORDER = {key: index for index, (key, *_) in enumerate(KINDS)}
# The games of a bar, said in its title: "Fléchettes et billard : Le Dernier Bar".
# Table football is in so many bars that it makes none a destination.
_BAR_GAMES = {"darts": "Fléchettes", "billiards": "Billard", "shuffleboard": "Palets"}


def _sports(tags: dict[str, str]) -> set[str]:
    return {sport.strip() for sport in tags.get("sport", "").split(";")}


def kind_of(tags: dict[str, str]) -> tuple[str, str, str, str] | None:
    """(key, title word, pattern of a name that says it, category words) of a venue, or None for another kind."""
    return next(((key, label, said, words) for key, label, said, words, test in KINDS if test(tags)), None)


def fetch_venues(client: httpx.Client) -> list[dict[str, Any]]:
    """Named leisure venues of Paris, with a website unless they are bars, rarest kinds first."""
    venues = []
    for element in overpass(client, OVERPASS_QUERY):
        tags = element.get("tags") or {}
        if (kind := kind_of(tags)) and (_website(tags) or kind[0] == "bar_games"):
            venues.append(element | {"kind": kind[0]})
    return sorted(venues, key=lambda e: (_ORDER[e["kind"]], e["type"], e["id"]))


def facts(place: dict[str, Any], site: dict[str, Any]) -> dict[str, Any]:
    tags = place.get("tags") or {}
    centre = place.get("center") or place
    key, label, _, words = kind_of(tags) or (None, "", "", "")
    name = tags.get("name") or ""
    sports = [s.strip() for s in tags.get("sport", "").split(";") if s.strip()]
    if key == "bar_games":
        games = [_BAR_GAMES[s] for s in sports if s in _BAR_GAMES]
        label = " et ".join([games[0], *[g.lower() for g in games[1:]]]) if games else ""
    # The name alone says little of the outing ("Arkose", "Le Dernier Bar"): the kind first, unless it says one ("Mad Golf").
    title = f"{label} : {name}" if label and not any(re.search(p, name, re.IGNORECASE) for _, _, p, _, _ in KINDS) else name
    return {
        "osm_id": f"{place['type']}/{place['id']}",
        "kind": key,
        "name": title,
        "venue_name": name,
        "address": " ".join(filter(None, [tags.get("addr:housenumber"), tags.get("addr:street")])) or None,
        "postal_code": tags.get("addr:postcode"),
        "latitude": centre.get("lat"),
        "longitude": centre.get("lon"),
        "website": _website(tags),
        "opening_hours": tags.get("opening_hours"),
        "evening": open_late(tags.get("opening_hours")),
        "category_text": words,
        **site,
    }


def open_late(opening_hours: str | None) -> bool | None:
    """Open in the evening: some day closes at 9 pm or later, or after midnight ("Mo-Su 10:00-23:30")."""
    closings = [int(hour) for hour in _CLOSING.findall(opening_hours or "")]
    return any(hour >= 21 or hour < 6 for hour in closings) if closings else None


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(
        source_id=SOURCE_ID,
        external_id=payload["osm_id"],
        url=safe_url(f"https://www.openstreetmap.org/{payload['osm_id']}"),
        payload=payload,
    )


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    raw = to_raw_record(payload)
    # A bar needs no booking: require_booking keeps it while open.
    if payload.get("kind") != "bar_games":
        if payload.get("site_error"):
            return Normalized(raw, rejection=f"site {payload['site_error']}")
        if not payload.get("engine"):
            return Normalized(raw, rejection="sans réservation en ligne")
    return normalize_facts(raw, complete_place(payload), "OpenStreetMap (ODbL)", now)


def collect(client: httpx.Client, now: datetime | None = None) -> Iterator[Normalized]:
    now = now or utc_now()
    venues = fetch_venues(client)
    with httpx.Client(timeout=20, follow_redirects=True, headers=BROWSER_HEADERS) as sites, ThreadPoolExecutor(WORKERS) as pool:
        # Batches keep --limit meaningful: the next websites are read only when asked for.
        for start in range(0, len(venues), BATCH):
            batch = venues[start : start + BATCH]
            read = pool.map(lambda venue: _read(sites, _website(venue["tags"])), batch)
            for venue, site in zip(batch, read):
                yield normalize(facts(venue, site), now)


def _read(client: httpx.Client, url: str | None) -> dict[str, Any]:
    return read_site(client, url) if url else {}


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
