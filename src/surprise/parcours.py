"""Evening routes: three different evenings for a couple, from a date, a budget, hours and vibes.

Every step of a route is free or bookable that evening, checked as far as the
sources allow:
- a dated show that evening (concerts.paris sessions, Que Faire à Paris,
  Shotgun, Eventbrite…), bookable through its ticketing link or free;
- a slot confirmed live on the booking engine (Funbooker, Wecandoo, Come to
  Paris, Zenchef, SevenRooms, 4escape), for two people, cached a few hours;
- a free place open at that time (opening hours known);
- a bar or club open at that time, walked into without booking (kept on
  purpose in the base), marked as such; --strict leaves them out. A dinner
  always has a table confirmed by the restaurant's booking engine.
Runs whose evenings are unknown (a play "until December") are left out.

The steps are chained in time and space: each one starts after the previous one
ends plus the walk or ride between them, without a long wait. Routes are built
by a beam search that favours the asked vibes, romance and originality, fills
the evening, keeps to the budget and walks rather than rides. Three routes are
kept, with no activity nor venue in common. Claude names them and writes their
pitch when ANTHROPIC_API_KEY is set; otherwise they are named by rules.

The result is a page with the three routes as timelines (photos, times, walks,
booking links), written to data/parcours/.
"""

import argparse
import html
import json
import math
import os
import pickle
import re
import sys
import time as clock
import webbrowser
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx

from surprise import availability, images
from surprise.collectors import come_to_paris, funbooker, wecandoo
from surprise.collectors.common import GROUP_PARTY
from surprise.local_store import DEFAULT_PATH, LocalStore
from surprise.originality import Scorer
from surprise.sources import source_name
from surprise.tags import TAGS, VIBES, describe

PARIS = ZoneInfo("Europe/Paris")
OUTPUT_DIR = Path("data/parcours")
CACHE_HOURS = 6
WALK_KM = 1.3  # about 20 minutes on foot
DEFAULT_MODEL = "claude-opus-5-5"

# Minutes an activity lasts when the source does not say.
_DURATIONS = [
    ("restaurant", 105), ("cabaret", 120), ("nuit", 180), ("atelier", 120), ("theatre", 90), ("humour", 80),
    ("concert", 90), ("spectacle", 90), ("croisiere", 75), ("bien_etre", 90), ("jeux", 75), ("visite", 90),
    ("expo", 75), ("musee", 90), ("bar", 75), ("cinema", 110),
]
# Price for two when a walk-in place gives none.
_ESTIMATES = {"repas": 90, "verre": 30, "sortie": 40}
# When a walk-in place gives no hours: when couples usually go, and until when.
# When a dinner may start: not a table at 23:00 after the show.
DINNER_HOURS = (time(18, 30), time(21, 30))
_USUAL_HOURS = {"verre": (time(18), time(1, 30)), "club": (time(23), time(5))}
_ROMANTIC_TAGS = {"chandelles", "vue", "sur_l_eau", "en_duo", "cache", "chic", "jazz", "classique", "eglise", "dans_le_noir", "gastronomique", "massage"}
_ROMANTIC_WORDS = {"romantique", "intimiste", "cosy", "aux chandelles", "vue panoramique", "coucher de soleil", "en duo"}
_DULL = {"salon", "conference"}
_CHECKED_SOURCES = {funbooker.SOURCE_ID, come_to_paris.SOURCE_ID, wecandoo.SOURCE_ID}
_PLATFORMS = _CHECKED_SOURCES | {"getyourguide", "tiqets", "civitatis", "explore_paris", "fever", "paris_jetaime_billetterie", "eventbrite", "shotgun", "billetreduc"}
# Links that point straight at a restaurant or game booking engine checked by surprise.availability.
_ENGINE_LINK = re.compile(r"zenchef|sevenrooms|4escape", re.IGNORECASE)
_QUARTERS = {
    1: "Louvre", 2: "Bourse", 3: "Haut-Marais", 4: "Marais", 5: "Quartier latin", 6: "Saint-Germain",
    7: "Tour Eiffel", 8: "Champs-Élysées", 9: "Pigalle–Opéra", 10: "Canal Saint-Martin", 11: "Bastille–Oberkampf",
    12: "Bercy", 13: "Butte-aux-Cailles", 14: "Montparnasse", 15: "Vaugirard", 16: "Passy", 17: "Batignolles",
    18: "Montmartre", 19: "Buttes-Chaumont", 20: "Belleville",
}
_ENGINE_NAMES = {"zenchef": "Zenchef", "sevenrooms": "SevenRooms", "4escape": "4escape"}
_DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


@dataclass
class Request:
    day: date
    budget: float  # euros for two
    start: datetime
    end: datetime
    vibes: list[str]
    party: int = 2
    walk_in: bool = True  # bars and clubs without booking may be steps
    trame: list[str] = field(default_factory=list)  # the steps asked, in order ("apero", "insolite", "fete")
    max_travel: int = 35  # minutes between two steps
    audace: float = 0.5  # 0: classics are fine, 1: only the unusual (questionnaire)
    avoid: set[str] = field(default_factory=set)  # tags, keywords or categories the couple refuses ("dans_le_noir", "sensations")
    prefer: set[str] = field(default_factory=set)  # tags the couple likes ("jazz", "electro")
    dinner: bool = False  # the couple wants a sit-down dinner in the evening


@dataclass
class Candidate:
    item: dict[str, Any]
    title: str
    venue: str
    arrondissement: int | None
    lat: float
    lon: float
    tags: list[str]
    vibes: list[str]
    role: str  # "repas", "verre" or "sortie"
    duration: int
    price: float  # for two
    price_estimated: bool
    starts: list[datetime]
    basis: str  # why it is bookable that evening
    kind: str  # "verifie", "seance", "gratuit", "sans_resa"
    booking_url: str | None
    ends: dict[datetime, datetime] = field(default_factory=dict)  # known end of a session
    flexible: bool = False  # walk-in: can leave earlier to fit the evening
    originality: int = 35  # surprise.originality, 0-100
    keywords: list[str] = field(default_factory=list)
    score: float = 0.0

    @property
    def key(self) -> tuple[str, str]:
        return self.item["source_id"], self.item["external_id"]

    def end_of(self, start: datetime) -> datetime:
        return self.ends.get(start) or start + timedelta(minutes=self.duration)


@dataclass
class Step:
    candidate: Candidate
    start: datetime
    end: datetime
    travel: int = 0  # minutes from the previous step
    distance: float = 0.0  # km from the previous step

    @property
    def basis(self) -> str:
        """Why the step is sure that evening, with the session chosen."""
        if self.candidate.kind == "seance":
            return f"Séance de {self.start:%H:%M} · {self.candidate.basis}"
        if self.candidate.kind == "verifie":
            return f"Créneau de {self.start:%H:%M} · {self.candidate.basis}"
        return self.candidate.basis


@dataclass
class Route:
    steps: list[Step]
    score: float = 0.0
    title: str = ""
    pitch: str = ""
    request: Request | None = None  # the evening asked, when several are planned together

    @property
    def price(self) -> float:
        return sum(step.candidate.price for step in self.steps)


# Time and place -------------------------------------------------------------


def window(day: date, start: str, end: str) -> tuple[datetime, datetime]:
    """The evening's bounds; an end before the start is the next morning."""
    begin = datetime.combine(day, time.fromisoformat(start), PARIS)
    finish = datetime.combine(day, time.fromisoformat(end), PARIS)
    return begin, finish + timedelta(days=1) if finish <= begin else finish


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def travel_minutes(km: float) -> int:
    """On foot up to WALK_KM (streets are not straight), else metro or taxi, waiting included."""
    if km <= WALK_KM:
        return max(3, round(km * 1.3 / 4.5 * 60))
    return round(12 + km * 1.3 / 20 * 60)


def opening_intervals(spec: str | None, day: date) -> list[tuple[datetime, datetime]] | None:
    """Opening intervals of the day from an OpenStreetMap opening_hours value; None when it cannot be read."""
    if not spec or not spec.strip():
        return None
    weekday = _DAYS[day.weekday()]
    hours: list[tuple[time, time]] | None = None
    for rule in filter(None, (part.strip() for part in spec.split(";"))):
        if rule == "24/7":
            hours = [(time(0), time(23, 59))]
            continue
        match = re.match(r"^((?:(?:Mo|Tu|We|Th|Fr|Sa|Su)(?:-(?:Mo|Tu|We|Th|Fr|Sa|Su))?,?\s*)+)?(.*)$", rule)
        days_part, times_part = (match.group(1) or "").strip(), match.group(2).strip()
        if days_part and weekday not in _expand_days(days_part):
            continue
        if times_part in ("off", "closed"):
            hours = []
            continue
        ranges = re.findall(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", times_part)
        if not ranges or re.search(r"[A-Za-z]{3,}|PH|week|\[", times_part.replace("off", "")):
            return None
        hours = [(time(int(a) % 24, int(b)), time(int(c) % 24, int(d))) for a, b, c, d in ranges]
    if hours is None:
        return []
    intervals = []
    for opens, closes in hours:
        begin = datetime.combine(day, opens, PARIS)
        finish = datetime.combine(day, closes, PARIS)
        intervals.append((begin, finish + timedelta(days=1) if finish <= begin else finish))
    return intervals


def _expand_days(spec: str) -> set[str]:
    days = set()
    for part in re.split(r"[,\s]+", spec):
        if "-" in part:
            first, last = (_DAYS.index(d) for d in part.split("-"))
            span = range(first, last + 1) if first <= last else [*range(first, 7), *range(0, last + 1)]
            days |= {_DAYS[i] for i in span}
        elif part:
            days.add(part)
    return days


# Candidates -----------------------------------------------------------------


def role(activity: dict[str, Any], tags: list[str]) -> str:
    categories = set(activity.get("categories") or [])
    if "atelier" in categories:
        return "sortie"
    if "restaurant" in categories or "diner" in tags or ("gastronomique" in tags and not categories - {"gastronomie", "restaurant", "bar"}):
        return "repas"
    if "bar" in categories and not categories & {"concert", "humour", "theatre", "spectacle", "cabaret", "nuit"}:
        return "verre"
    return "sortie"


def default_duration(activity: dict[str, Any], role_: str) -> int:
    if activity.get("duration_minutes"):
        return int(activity["duration_minutes"])
    categories = set(activity.get("categories") or [])
    if role_ == "repas":
        return 105
    return next((minutes for category, minutes in _DURATIONS if category in categories), 90)


def price_for_two(activity: dict[str, Any], role_: str) -> tuple[float, bool]:
    """Cheapest price for two, and whether it is a guess."""
    offers = activity.get("offers") or []
    if any(offer.get("is_free") for offer in offers):
        return 0.0, False
    prices = [
        float(offer["price_min"]) * (1 if offer.get("price_unit") in ("per_couple", "per_group") else 2)
        for offer in offers
        if offer.get("price_min") is not None
    ]
    if prices and min(prices) > 0:
        return min(prices), False
    return float(_ESTIMATES[role_]), True


def booking_url(item: dict[str, Any]) -> str | None:
    links = [offer.get("booking_url") for offer in item["activity"].get("offers") or []]
    return next(filter(None, links), None) or item["enrichment"].get("booking_url")


def coordinates(item: dict[str, Any]) -> tuple[float, float] | None:
    venue = item["activity"].get("venue") or {}
    lat = venue.get("latitude") or item["enrichment"].get("latitude")
    lon = venue.get("longitude") or item["enrichment"].get("longitude")
    return (float(lat), float(lon)) if lat and lon else None


def needs_check(item: dict[str, Any]) -> bool:
    """An activity without dated sessions whose engine answers for a date."""
    activity = item["activity"]
    if activity.get("occurrences"):
        return False
    if item["source_id"] in _CHECKED_SOURCES:
        return True
    links = " ".join(filter(None, [booking_url(item), str(activity.get("website") or "")]))
    if not links:
        return False
    return bool(_ENGINE_LINK.search(links)) or bool({"restaurant", "jeux"} & set(activity.get("categories") or []))


def build_candidate(item: dict[str, Any], request: Request, checked: dict[str, Any] | None, originality: int = 35) -> Candidate | None:
    """The activity as a step of the evening, with its possible start times, or None if it cannot be one.

    Never a stag or hen party offer (collected before the rule); a dinner sits down between 18:30 and 21:30.
    """
    activity = item["activity"]
    if GROUP_PARTY.search(" ".join(filter(None, [activity["title"], (activity.get("venue") or {}).get("name")]))):
        return None
    candidate = _build_candidate(item, request, checked, originality)
    if candidate and candidate.role == "repas":
        candidate.starts = [s for s in candidate.starts if DINNER_HOURS[0] <= s.time() <= DINNER_HOURS[1] and s.date() == request.day]
        if not candidate.starts:
            return None
    return candidate


def _build_candidate(item: dict[str, Any], request: Request, checked: dict[str, Any] | None, originality: int) -> Candidate | None:
    activity = item["activity"]
    place = coordinates(item)
    if not place:
        return None
    found = describe(activity)
    role_ = role(activity, found["tags"])
    duration = default_duration(activity, role_)
    price, estimated = price_for_two(activity, role_)
    free = price == 0 and not estimated
    link = booking_url(item)
    venue = activity.get("venue") or {}
    base = dict(
        item=item, title=activity["title"], venue=venue.get("name") or "", arrondissement=venue.get("arrondissement"),
        lat=place[0], lon=place[1], tags=found["tags"], vibes=found["vibes"], role=role_, duration=duration,
        price=price, price_estimated=estimated, booking_url=link,
        originality=originality, keywords=item["enrichment"].get("keywords") or [],
    )
    latest = request.end - timedelta(minutes=30)
    categories = set(activity.get("categories") or [])

    # Dated sessions that evening.
    sessions = []
    for occurrence in activity.get("occurrences") or []:
        begin = datetime.fromisoformat(occurrence["starts_at"]).astimezone(PARIS)
        if request.start <= begin <= latest:
            finish = datetime.fromisoformat(occurrence["ends_at"]).astimezone(PARIS) if occurrence.get("ends_at") else None
            sessions.append((begin, finish if finish and finish - begin <= timedelta(hours=6) else None))
    if sessions:
        if not (free or link):
            return None
        ends = {begin: finish for begin, finish in sessions if finish}
        dancing = "nuit" in categories or "fete" in found["vibes"]  # one leaves when the evening ends
        basis = "Gratuit" if free else f"billets sur {_platform(link)}"
        return Candidate(**base, starts=[b for b, _ in sessions], ends=ends, basis=basis, kind="gratuit" if free else "seance", flexible=dancing)
    if activity.get("occurrences"):
        return None  # dated, but not this evening

    # A slot confirmed by the booking engine.
    if checked and checked.get("engine"):
        if not checked.get("available"):
            return None
        starts, ends = [], {}
        for slot in checked["slots"]:
            if slot == "journée":
                starts += _grid(request.start, min(latest, datetime.combine(request.day, time(20), PARIS)))
                continue
            begin = datetime.combine(request.day, time.fromisoformat(slot[:5]), PARIS)
            if begin < request.start - timedelta(hours=6):
                begin += timedelta(days=1)  # after midnight
            if request.start <= begin <= latest:
                starts.append(begin)
                if len(slot) == 11:
                    finish = datetime.combine(request.day, time.fromisoformat(slot[6:]), PARIS)
                    ends[begin] = finish if finish > begin else finish + timedelta(days=1)
        if not starts:
            return None
        engine = _ENGINE_NAMES.get(checked["engine"], checked["engine"])
        # The formula booked (Funbooker, Come to Paris); a restaurant's services say nothing to the couple.
        detail = f" · {checked['detail']}" if checked.get("detail") and engine not in _ENGINE_NAMES.values() and len(checked["detail"]) < 60 else ""
        return Candidate(**base, starts=sorted(set(starts)), ends=ends, basis=f"libre pour 2, vérifié sur {engine}{detail}", kind="verifie")

    if activity.get("kind") == "temporary":
        return None  # a run without its evenings: cannot tell whether it plays that day

    hours = opening_intervals(item["enrichment"].get("opening_hours") or _venue_hours(venue), request.day)
    # Bars and clubs are walked into; a dinner is only proposed with a table confirmed above.
    # A booking platform's listing ("Soirée jeux de société" on Funbooker) is an offer to book, not a place to walk in.
    walk_in = request.walk_in and role_ != "repas" and categories & {"bar", "nuit"} and item["source_id"] not in _PLATFORMS
    walk_in = walk_in and not {"visite_guidee", "sur_l_eau"} & set(found["tags"])  # a night tour is booked, not walked into
    if walk_in:
        usual = hours is None
        if usual:
            opens, closes = _USUAL_HOURS["club" if role_ == "sortie" else "verre"]
            hours = [(datetime.combine(request.day, opens, PARIS), datetime.combine(request.day, closes, PARIS))]
            hours = [(a, b + timedelta(days=1) if b <= a else b) for a, b in hours]
        starts = [s for a, b in hours for s in _grid(max(a, request.start), min(b - timedelta(minutes=45), latest))]
        if not starts:
            return None
        basis = "Sans réservation" + (" · horaires habituels, à confirmer" if usual else " · ouvert à cette heure")
        return Candidate(**base, starts=starts, basis=basis, kind="sans_resa", flexible=True)

    if free and hours:
        starts = [s for a, b in hours for s in _grid(max(a, request.start), min(b - timedelta(minutes=duration), latest))]
        if starts:
            return Candidate(**base, starts=starts, basis="Gratuit · ouvert à cette heure", kind="gratuit")
    return None


def _venue_hours(venue: dict[str, Any]) -> str | None:
    hours = venue.get("opening_hours")
    return hours if isinstance(hours, str) else (hours or {}).get("osm") if isinstance(hours, dict) else None


def _grid(begin: datetime, finish: datetime, step: int = 15) -> list[datetime]:
    """Start times every quarter of an hour."""
    begin = begin + timedelta(minutes=(-begin.minute) % step)
    times = []
    while begin <= finish:
        times.append(begin)
        begin += timedelta(minutes=step)
    return times


def _platform(url: str | None) -> str:
    from surprise.booking import engine_in

    return (engine_in(url) if url else None) or "billetterie en ligne"


def score(candidate: Candidate, request: Request) -> float:
    """How well the activity answers the request, on its own."""
    item, activity = candidate.item, candidate.item["activity"]
    asked = set(request.vibes)
    matched = asked & set(candidate.vibes)
    value = 4 * len(matched) / len(asked) if asked else 2
    if candidate.role == "sortie" and asked and not matched:
        return -math.inf  # an outing must answer one of the wishes
    if request.avoid & (set(candidate.tags) | set(candidate.keywords) | set(activity.get("categories") or [])):
        return -math.inf  # the couple said no
    if "romantique" in candidate.vibes:
        value += 1.2
    value += min(2, 0.5 * len(_ROMANTIC_TAGS & set(candidate.tags)))
    value += min(1.2, 0.4 * len(_ROMANTIC_WORDS & set(candidate.keywords)))
    if request.prefer & set(candidate.tags):
        value += 1
    # Originality counts more for a daring couple (surprise.originality: offbeat, rare, curated, not a classic).
    value += (candidate.originality - 35) / 25 * (0.5 + request.audace)
    if _DULL & set(activity.get("categories") or []):
        value -= 1.5
    if item["enrichment"].get("image_url") or activity.get("image"):
        value += 0.6
    else:
        value -= 1
    value += {"verifie": 0.6, "seance": 0.4, "gratuit": 0.2, "sans_resa": -0.3}[candidate.kind]
    if "à confirmer" in candidate.basis:
        value -= 0.5
    if item["status"] == "approved":
        value += 0.5
    if candidate.price > request.budget:
        value -= 3
    return value


# Checking the engines -------------------------------------------------------


def check_engines(store: LocalStore, items: list[dict[str, Any]], request: Request, limit: int, prescore: dict) -> dict:
    """Engine answers for the date: cached ones, then live checks of the best `limit` activities not yet asked."""
    day = request.day.isoformat()
    cached = store.cached_availability(day, request.party, CACHE_HOURS)
    todo = sorted(
        (item for item in items if needs_check(item) and (item["source_id"], item["external_id"]) not in cached),
        key=lambda item: -prescore.get((item["source_id"], item["external_id"]), 0),
    )
    # Half of the checks for dinners, the rarest step to confirm.
    dinners = [item for item in todo if role(item["activity"], describe(item["activity"])["tags"]) == "repas"]
    others = [item for item in todo if item not in dinners]
    taken = min(len(dinners), limit // 2)
    todo = dinners[:taken] + others[: limit - taken]
    if todo:
        print(f"Vérification de {len(todo)} disponibilités (moteurs de réservation)…")
    with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": availability.USER_AGENT}) as client:
        for index, item in enumerate(todo, 1):
            try:
                found = availability.check(client, item, request.day, request.party)
            except (httpx.HTTPError, ValueError, KeyError) as error:
                found = "?", availability.Availability(None, detail=f"erreur : {error}"[:200])
            engine, result = found or (None, availability.Availability(None, detail="sans moteur pris en charge"))
            store.save_availability(item["source_id"], item["external_id"], day, request.party, engine, result.available, result.slots, result.detail)
            cached[(item["source_id"], item["external_id"])] = {"engine": engine, "available": result.available, "slots": result.slots, "detail": result.detail}
            mark = {True: "✓", False: "✗", None: "·"}[result.available]
            print(f"  {index:>3}/{len(todo)} {mark} {item['activity']['title'][:70]}")
            clock.sleep(availability.DELAY_SECONDS / 2)
    return cached


def quick_score(item: dict[str, Any], request: Request, originality: int = 35) -> float:
    """Ranking before any check: vibes, romance, originality and a photo."""
    found = describe(item["activity"])
    asked = set(request.vibes)
    value = 4 * len(asked & set(found["vibes"])) / len(asked) if asked else 1
    value += 1.2 * ("romantique" in found["vibes"])
    value += 0.5 * len(_ROMANTIC_TAGS & set(found["tags"]))
    value += 0.6 * bool(item["enrichment"].get("image_url") or item["activity"].get("image"))
    value += (originality - 35) / 25 * (0.5 + request.audace)
    return value


# Composing the routes -------------------------------------------------------

# Steps a route can be asked to follow, besides the vibes ("insolite": an outing with that vibe).
SLOTS = {
    "apero": "un verre en début de soirée (bar, cave, cocktails)",
    "diner": "un dîner, table confirmée",
    "fete": "danser : club, boîte, bar dansant, soirée DJ",
}


def fits_slot(candidate: Candidate, slot: str, start: datetime) -> bool:
    """The candidate can be this step of the asked trame, starting then."""
    categories = set(candidate.item["activity"].get("categories") or [])
    if slot == "apero":
        drinks = candidate.role == "verre" or ({"mixologie", "vin", "degustation"} & set(candidate.tags) and candidate.role != "repas")
        return bool(drinks) and "nuit" not in categories and "fete" not in candidate.vibes and start.time() <= time(21)
    if slot == "diner":
        return candidate.role == "repas"
    if slot == "fete":
        dancing = "fete" in candidate.vibes or "nuit" in categories or "danse" in candidate.tags
        seated = {"jeux_de_societe", "escape_game", "quiz", "murder_party", "visite_guidee", "theatre"} & set(candidate.tags)
        return dancing and not seated and candidate.role != "repas" and (start.time() >= time(21, 30) or start.time() < time(6))
    return candidate.role == "sortie" and slot in candidate.vibes and "fete" not in candidate.vibes


def compose(candidates: list[Candidate], request: Request, beam: int = 300, max_steps: int = 4) -> list[Route]:
    """Routes that chain the activities through the evening, best first."""
    pool = _shortlist(candidates)
    finished: list[Route] = []
    states = []
    trame = request.trame
    if trame:
        max_steps = len(trame)
    for candidate in pool:
        # A bar can be the start at 19:00 as well as at 20:00; a show, at each of its sessions.
        starts = [
            s for s in candidate.starts
            if s <= request.start + timedelta(minutes=90) and (not trame or fits_slot(candidate, trame[0], s))
        ]
        if candidate.flexible:
            starts = [s for s in starts if s.minute % 30 == 0]
        states += [[_step(candidate, start, request)] for start in starts[:4]]
    for _ in range(max_steps):
        states = sorted(states, key=lambda steps: -_route_score(steps, request, partial=True))[:beam]
        finished += [Route(steps) for steps in states if _complete(steps, request)]
        grown = []
        for steps in states:
            last = steps[-1]
            if last.end >= request.end - timedelta(minutes=30):
                continue
            used = {s.candidate.key for s in steps}
            venues = {s.candidate.venue.lower() for s in steps}
            roles = Counter(s.candidate.role for s in steps)
            slot = trame[len(steps)] if len(steps) < len(trame) else None
            if trame and slot is None:
                continue
            for candidate in pool:
                if candidate.key in used or candidate.venue.lower() in venues or not _role_fits(candidate, roles, steps, bool(trame)):
                    continue
                km = distance_km((last.candidate.lat, last.candidate.lon), (candidate.lat, candidate.lon))
                minutes = travel_minutes(km)
                if minutes > request.max_travel:
                    continue
                ready = last.end + timedelta(minutes=minutes + 5)
                # Clubs open late: a longer walk or wait before them is part of the night.
                wait = timedelta(minutes=90 if slot == "fete" else 60 if trame else 50)
                # A bar can be left earlier to catch a session, after 45 minutes at least.
                earliest = last.start + timedelta(minutes=45 + minutes + 5) if last.candidate.flexible else ready
                fitting = [s for s in candidate.starts if earliest <= s <= ready + wait and (not slot or fits_slot(candidate, slot, s))]
                if not fitting:
                    continue
                start = next((s for s in fitting if s >= ready), fitting[-1])
                previous = last
                if start < ready:
                    leave = start - timedelta(minutes=minutes + 5)
                    leave -= timedelta(minutes=leave.minute % 5)
                    previous = Step(last.candidate, last.start, leave, last.travel, last.distance)
                step = _step(candidate, start, request, travel=minutes, distance=km)
                if step.end > request.end + timedelta(minutes=20) or step.end - step.start < timedelta(minutes=40):
                    continue
                grown.append(steps[:-1] + [previous, step])
        if not grown:
            break
        states = grown
    finished += [Route(steps) for steps in states if _complete(steps, request)]
    for route in finished:
        route.score = _route_score(route.steps, request)
    return sorted((route for route in finished if route.score > -math.inf), key=lambda route: -route.score)


def _shortlist(candidates: list[Candidate]) -> list[Candidate]:
    """The best candidates of each role, to keep the search quick."""
    by_role: dict[str, list[Candidate]] = {}
    for candidate in sorted(candidates, key=lambda c: -c.score):
        by_role.setdefault(candidate.role, []).append(candidate)
    limits = {"sortie": 180, "repas": 60, "verre": 60}
    return [c for role_, group in by_role.items() for c in group[: limits[role_]]]


def _step(candidate: Candidate, start: datetime, request: Request, travel: int = 0, distance: float = 0.0) -> Step:
    end = candidate.end_of(start)
    if candidate.flexible:
        end = min(end, request.end)  # leave the bar at the end of the evening
    return Step(candidate, start, end, travel, distance)


def _role_fits(candidate: Candidate, roles: Counter, steps: list[Step], trame: bool = False) -> bool:
    """Without a trame: one dinner, one drink, three outings at most. Always: no kind of outing twice."""
    if not trame and candidate.role in ("repas", "verre") and roles[candidate.role]:
        return False
    if not trame and candidate.role == "sortie" and roles["sortie"] >= 3:
        return False
    # Not twice the same kind of outing (two escape games, two stand-ups).
    kinds = _activity_tags(candidate)
    if any(kinds & _activity_tags(s.candidate) for s in steps):
        return False
    # One boat and one view are enough for an evening.
    settings = {"sur_l_eau", "vue"} & set(candidate.tags)
    return not any(settings & set(s.candidate.tags) for s in steps)


def _activity_tags(candidate: Candidate) -> set[str]:
    return {t for t in candidate.tags if TAGS[t]["facet"] == "activite"}


def _main_tag(candidate: Candidate) -> str | None:
    """What the outing mainly is: its first activity tag."""
    return next((t for t in candidate.tags if TAGS[t]["facet"] == "activite"), None)


def _complete(steps: list[Step], request: Request) -> bool:
    """Every step of the trame; else at least two steps, an outing, and an evening mostly filled."""
    if request.trame:
        return len(steps) == len(request.trame)
    if len(steps) < 2 or not any(s.candidate.role == "sortie" for s in steps):
        return False
    return steps[-1].end >= request.end - timedelta(minutes=100)


def _route_score(steps: list[Step], request: Request, partial: bool = False) -> float:
    value = sum(step.candidate.score for step in steps)
    asked = set(request.vibes)
    if asked:
        covered = asked & {v for step in steps for v in step.candidate.vibes}
        value += 3 * len(covered) / len(asked)
    travel = sum(step.travel for step in steps)
    idle = sum(
        max(0, (step.start - previous.end).total_seconds() / 60 - step.travel - 5)
        for previous, step in zip(steps, steps[1:])
    )
    value -= 0.06 * travel + 0.05 * idle
    value -= 0.5 * sum(step.distance > WALK_KM for step in steps)  # a ride rather than a walk
    price = sum(step.candidate.price for step in steps)
    if price > request.budget * 1.2:
        return -math.inf
    if price > request.budget:
        value -= 6 * (price - request.budget) / request.budget
    if any(s.candidate.role == "repas" and time(19) <= s.start.time() <= time(21, 30) for s in steps):
        value += 1
    if not partial:
        last = steps[-1].candidate
        if last.role == "verre" or {"vue", "nocturne", "sur_l_eau"} & set(last.tags) or "fete" in last.vibes:
            value += 0.8
        if steps[0].start > request.start + timedelta(minutes=45):
            value -= 1
        value -= 0.02 * max(0, (request.end - steps[-1].end).total_seconds() / 60)
        value -= 0.4 * sum(s.candidate.kind == "sans_resa" for s in steps)
        if request.dinner and not any(s.candidate.role == "repas" for s in steps):
            value -= 3
    return value


def pick(routes: list[Route], count: int = 3, taken: list[Route] | None = None) -> list[Route]:
    """The best routes that share no activity nor venue, and differ in area and in kind of outing.

    `taken`: routes already on the page, which the new ones must differ from.
    """
    chosen: list[Route] = list(taken or [])
    count += len(chosen)
    remaining = routes[:5000]
    while remaining and len(chosen) < count:
        best, best_value = None, -math.inf
        for route in remaining:
            keys = {s.candidate.key for s in route.steps}
            venues = {s.candidate.venue.lower() for s in route.steps}
            if any(keys & {s.candidate.key for s in c.steps} or venues & {s.candidate.venue.lower() for s in c.steps} for c in chosen):
                continue
            value = route.score - sum(_similarity(route, other) for other in chosen)
            if value > best_value:
                best, best_value = route, value
        if best is None:
            break
        chosen.append(best)
        remaining = [r for r in remaining if r is not best]
    return chosen[len(taken or []):]


def _similarity(a: Route, b: Route) -> float:
    tags_a = {_main_tag(s.candidate) for s in a.steps} - {None}
    tags_b = {_main_tag(s.candidate) for s in b.steps} - {None}
    if a.steps[0].start.date() != b.steps[0].start.date():
        return 1.5 * len(tags_a & tags_b)  # the same area another evening is no repeat
    km = distance_km(_centre(a), _centre(b))
    return 1.5 * len(tags_a & tags_b) + (2 if km < 1.2 else 1 if km < 2.5 else 0)


def _centre(route: Route) -> tuple[float, float]:
    return (
        sum(s.candidate.lat for s in route.steps) / len(route.steps),
        sum(s.candidate.lon for s in route.steps) / len(route.steps),
    )


def replace_step(route: Route, position: int, candidates: list[Candidate], request: Request, excluded: set) -> list[Step] | None:
    """The route's steps with another activity at this position, the others kept; None if nothing fits.

    The new activity plays the same part (the trame's step, or else the same role), chains with
    the steps around it in time and distance, and keeps the evening within budget. A bar or club
    around it is left earlier, or joined later, to make room.
    """
    steps = route.steps
    old = steps[position]
    others = steps[:position] + steps[position + 1 :]
    previous = steps[position - 1] if position else None
    following = steps[position + 1] if position + 1 < len(steps) else None
    slot = request.trame[position] if position < len(request.trame) else None
    roles = Counter(s.candidate.role for s in others)
    venues = {s.candidate.venue.lower() for s in others}
    budget = request.budget * 1.2 - sum(s.candidate.price for s in others)
    wait = timedelta(minutes=90 if slot == "fete" else 60 if request.trame else 50)
    best, best_value = None, -math.inf
    for candidate in candidates:
        if candidate.key in excluded or candidate.venue.lower() in venues or candidate.price > budget:
            continue
        if (slot is None and candidate.role != old.candidate.role) or not _role_fits(candidate, roles, others, bool(request.trame)):
            continue
        km_in = distance_km((previous.candidate.lat, previous.candidate.lon), (candidate.lat, candidate.lon)) if previous else 0.0
        travel_in = travel_minutes(km_in) if previous else 0
        km_out = distance_km((candidate.lat, candidate.lon), (following.candidate.lat, following.candidate.lon)) if following else 0.0
        travel_out = travel_minutes(km_out) if following else 0
        if travel_in > request.max_travel or travel_out > request.max_travel:
            continue
        if previous:
            # A bar before can be left after 45 minutes, or stayed in longer.
            full = _step(previous.candidate, previous.start, request).end
            ready = (previous.start + timedelta(minutes=45) if previous.candidate.flexible else previous.end) + timedelta(minutes=travel_in + 5)
            latest = (full if previous.candidate.flexible else previous.end) + timedelta(minutes=travel_in + 5) + wait
        else:
            ready, latest = request.start, request.start + timedelta(minutes=90)
        for start in (s for s in candidate.starts if ready <= s <= latest and (not slot or fits_slot(candidate, slot, s))):
            if candidate.flexible and start.minute % 15:
                continue
            step = _step(candidate, start, request, travel_in, km_in)
            new_previous = previous
            if previous and previous.candidate.flexible:
                leave = min(full, start - timedelta(minutes=travel_in + 5))
                leave -= timedelta(minutes=leave.minute % 5)
                new_previous = Step(previous.candidate, previous.start, leave, previous.travel, previous.distance)
            new_following = following
            if following:
                needed = step.end + timedelta(minutes=travel_out + 5)
                if needed > following.start and candidate.flexible:
                    step.end = following.start - timedelta(minutes=travel_out + 5)
                    step.end -= timedelta(minutes=step.end.minute % 5)
                elif needed > following.start and following.candidate.flexible:
                    joined = needed + timedelta(minutes=-needed.minute % 5)
                    if following.end - joined < timedelta(minutes=45):
                        continue
                    new_following = Step(following.candidate, joined, following.end, travel_out, km_out)
                elif needed > following.start:
                    continue
                if new_following is following:
                    new_following = Step(following.candidate, following.start, following.end, travel_out, km_out)
                if new_following.start - step.end - timedelta(minutes=travel_out + 5) > wait:
                    continue
            elif step.end > request.end + timedelta(minutes=20):
                continue
            if step.end - step.start < timedelta(minutes=40):
                continue
            chain = steps[: max(0, position - 1)] + ([new_previous] if previous else []) + [step] + ([new_following] if following else []) + steps[position + 2 :]
            value = _route_score(chain, request)
            if value > best_value:
                best, best_value = chain, value
            break  # the earliest session that fits: later ones only add waiting
    return best


# Names and pitches ----------------------------------------------------------


def name_by_rules(route: Route, request: Request) -> None:
    arrondissements = Counter(s.candidate.arrondissement for s in route.steps if s.candidate.arrondissement)
    quarter = _QUARTERS.get(arrondissements.most_common(1)[0][0], "Paris") if arrondissements else "Paris"
    asked = [v for v in request.vibes if any(v in s.candidate.vibes for s in route.steps)]
    moods = asked or [v for v, _ in Counter(v for s in route.steps for v in s.candidate.vibes).most_common(2)]
    labels = [VIBES[v]["label"].lower() for v in moods[:2]]
    route.title = f"{' & '.join(labels).capitalize() or 'Soirée surprise'} · {quarter}"
    parts = []
    for index, step in enumerate(route.steps):
        what = step.candidate.title
        if index == 0:
            parts.append(f"On commence à {step.start:%H:%M} par « {what} »")
        else:
            how = f"{step.travel} min à pied" if step.distance <= WALK_KM else f"{step.travel} min en métro ou taxi"
            parts.append(f"puis, à {how}, « {what} »")
    route.pitch = ", ".join(parts) + "."


def name_with_claude(routes: list[Route], request: Request) -> bool:
    """Title and pitch of each route written by Claude; False when unavailable."""
    if not os.environ.get("ANTHROPIC_API_KEY") or not routes:
        return False
    import anthropic

    client = anthropic.Anthropic()
    summary = [
        {
            "parcours": index + 1,
            "etapes": [
                {
                    "heure": f"{s.start:%H:%M}-{s.end:%H:%M}",
                    "activite": s.candidate.title,
                    "lieu": s.candidate.venue,
                    "arrondissement": s.candidate.arrondissement,
                    "trajet_depuis_precedente": f"{s.travel} min" if index_step else None,
                    "texte": (s.candidate.item["enrichment"].get("description") or s.candidate.item.get("lead_text") or "")[:400],
                }
                for index_step, s in enumerate(route.steps)
            ],
        }
        for index, route in enumerate(routes)
    ]
    prompt = (
        f"Voici {len(routes)} parcours de soirée en couple à Paris le {request.day:%d/%m/%Y}, envies : "
        f"{', '.join(VIBES[v]['label'] for v in request.vibes) or 'libres'}.\n"
        + json.dumps(summary, ensure_ascii=False, indent=1)
        + "\n\nPour chaque parcours, donne un titre évocateur (6 mots au plus) et un pitch de 2 phrases, "
        "au présent, qui raconte la soirée comme un souvenir à partager, sans superlatifs creux ni inventer "
        "de détail absent des données. Réponds en JSON seul : "
        '[{"parcours": 1, "titre": "...", "pitch": "..."}]'
    )
    try:
        response = client.messages.create(
            model=os.environ.get("SURPRISE_LLM_MODEL", DEFAULT_MODEL),
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        named = json.loads(text[text.index("[") : text.rindex("]") + 1])
    except (anthropic.APIError, ValueError) as error:
        print(f"Claude indisponible ({error.__class__.__name__}) : titres par règles")
        return False
    for entry in named:
        index = int(entry.get("parcours", 0)) - 1
        if 0 <= index < len(routes) and entry.get("titre") and entry.get("pitch"):
            routes[index].title, routes[index].pitch = entry["titre"], entry["pitch"]
    return True


# Page -----------------------------------------------------------------------


def render(routes: list[Route], request: Request, days: list[date] | None = None, name: str = "") -> str:
    """The routes as timelines; with several evenings, each route says its date.

    Served by surprise.quiz, the page (its `name`) offers to draw a route or a step again.
    """
    days = days or [request.day]
    vibes = "".join(f'<span class="chip">{html.escape(VIBES[v]["label"])}</span>' for v in request.vibes)
    vibes += "".join(f'<span class="chip plain">{i + 1}. {html.escape(_SLOT_LABELS.get(s, VIBES.get(s, {}).get("label", s)))}</span>' for i, s in enumerate(request.trame))
    body = "".join(_render_route(index, route, request.vibes, dated=len(days) > 1) for index, route in enumerate(routes)) or (
        '<p class="empty">Aucun parcours complet ce soir-là avec ces critères. Élargissez les horaires, le budget ou les envies.</p>'
    )
    return _PAGE.format(
        title=f"Parcours du {days[0]:%d/%m/%Y}" + (f" au {days[-1]:%d/%m/%Y}" if len(days) > 1 else ""),
        count=_COUNTS.get(len(routes), str(len(routes))),
        day=" · ".join(f"{_weekday(d)} {d:%d/%m}" for d in days) if len(days) > 1 else f"{_weekday(request.day)} {request.day:%d/%m/%Y}",
        hours=f"{request.start:%H:%M} – {request.end:%H:%M}",
        budget=f"{request.budget:.0f} €",
        vibes=vibes,
        body=body,
        name=html.escape(name),
        script=_SCRIPT,
    )


def _render_route(index: int, route: Route, asked: list[str], dated: bool = False) -> str:
    steps = []
    for position, step in enumerate(route.steps):
        if position:
            previous = route.steps[position - 1].candidate
            mode = "walking" if step.distance <= WALK_KM else "transit"
            maps = "https://www.google.com/maps/dir/?" + urlencode(
                {"api": 1, "origin": f"{previous.lat},{previous.lon}", "destination": f"{step.candidate.lat},{step.candidate.lon}", "travelmode": mode}
            )
            icon = "🚶" if mode == "walking" else "🚇"
            label = f"{step.travel} min" + (f" · {step.distance * 1000:.0f} m" if step.distance < 1 else f" · {step.distance:.1f} km")
            steps.append(f'<a class="hop" href="{html.escape(maps)}" target="_blank" rel="noopener"><span>{icon}</span>{label}</a>')
        steps.append(_render_step(step, asked, f"routes/{index}/steps/{position}"))
    total = route.price
    estimated = any(s.candidate.price_estimated for s in route.steps)
    return f"""
<section class="route" id="parcours-{index + 1}">
  <header>
    <p class="eyebrow">Parcours {index + 1}{f" · {_weekday(route.steps[0].start.date())} {route.steps[0].start:%d/%m}" if dated else ""}
      <button type="button" class="redo" data-redo="routes/{index}" title="Composer une autre soirée à la place de celle-ci">↻ Tout le parcours</button></p>
    <h2>{html.escape(route.title)}</h2>
    <p class="pitch">{html.escape(route.pitch)}</p>
    <p class="meta"><span>{route.steps[0].start:%H:%M} → {route.steps[-1].end:%H:%M}</span>
      <span>{'≈ ' if estimated else ''}{total:.0f} € pour deux</span>
      <span>{len(route.steps)} étapes</span></p>
  </header>
  <ol class="timeline">{''.join(steps)}</ol>
</section>"""


def _render_step(step: Step, asked: list[str], redo: str = "") -> str:
    c = step.candidate
    item = c.item
    image = item["enrichment"].get("image_url") or ((item["activity"].get("image") or {}).get("url"))
    if images.needs_copy(image):
        copy = images.local_copy(image)
        image = f"../{copy.parent.name}/{copy.name}" if copy else None
    picture = f'<img src="{html.escape(image)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">' if image else ""
    text = item["enrichment"].get("description") or " ".join((item.get("lead_text") or "").split())
    if len(text) > 180:
        text = text[:177].rsplit(" ", 1)[0] + "…"
    price = "Gratuit" if c.price == 0 else f"{'≈ ' if c.price_estimated else ''}{c.price:.0f} € à deux"
    badge = {"verifie": "ok", "seance": "ok", "gratuit": "free", "sans_resa": "walk"}[c.kind]
    if c.kind == "sans_resa":
        link, label = str(item["activity"].get("website") or item.get("source_url") or ""), "Voir le lieu"
    elif c.price == 0:
        link, label = c.booking_url or item.get("source_url") or "", "Voir la fiche"
    else:
        link, label = c.booking_url or item.get("source_url") or "", "Réserver"
    button = f'<a class="book {"primary" if label == "Réserver" else ""}" href="{html.escape(link)}" target="_blank" rel="noopener">{label}</a>' if link else ""
    shown = [v for v in asked if v in c.vibes] + [v for v in c.vibes if v not in asked]
    vibes = "".join(f'<span class="tag{" asked" if v in asked else ""}">{html.escape(VIBES[v]["label"])}</span>' for v in shown[:3])
    vibes += "".join(f'<span class="tag word">{html.escape(word)}</span>' for word in c.keywords[:2])
    if c.originality >= 55:
        vibes += f'<span class="tag orig" title="originalité sur 100">✦ {c.originality}</span>'
    place = " · ".join(filter(None, [c.venue, f"Paris {c.arrondissement}ᵉ" if c.arrondissement else None]))
    return f"""
<li class="step">
  <div class="time">{step.start:%H:%M}<small>→ {step.end:%H:%M}</small></div>
  <article class="card">
    <div class="photo">{picture}<span class="role">{_ROLE_LABELS[c.role]}</span>{f'<button type="button" class="redo on-photo" data-redo="{redo}" title="Proposer une autre activité à cette étape">↻ Changer</button>' if redo else ''}</div>
    <div class="content">
      <h3>{html.escape(c.title)}</h3>
      <p class="place">{html.escape(place)}</p>
      {f'<p class="text">{html.escape(text)}</p>' if text else ''}
      <p class="tags">{vibes}</p>
      <p class="basis {badge}">{html.escape(step.basis)}</p>
      <div class="foot"><span class="price">{price}</span>{button}</div>
      <p class="source">via {html.escape(source_name(item['source_id']))}</p>
    </div>
  </article>
</li>"""


_SLOT_LABELS = {"apero": "Apéro", "diner": "Dîner", "fete": "Danser"}
_COUNTS = {1: "Une", 2: "Deux", 3: "Trois", 4: "Quatre", 5: "Cinq", 6: "Six", 7: "Sept", 8: "Huit", 9: "Neuf", 10: "Dix"}
_ROLE_LABELS = {"repas": "Dîner", "verre": "Un verre", "sortie": "Sortie"}


def _weekday(day: date) -> str:
    return ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"][day.weekday()]


_PAGE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{
  --bg: #faf7f4; --surface: #ffffff; --text: #231c1a; --muted: #6f6360; --line: #e8dfd9;
  --accent: #b3264b; --accent-soft: #f7e4e9; --ok: #1e7a4c; --ok-soft: #e3f3ea; --walk: #8a5a00; --walk-soft: #fbf0d9;
  --free: #1f5fa8; --free-soft: #e2edf9;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #171314; --surface: #221c1e; --text: #f3ecea; --muted: #b3a7a4; --line: #3a3033;
    --accent: #f06b8f; --accent-soft: #3b1f28; --ok: #6fd3a0; --ok-soft: #1b3226; --walk: #f0c46b; --walk-soft: #372b14;
    --free: #8fbef3; --free-soft: #1a2a3d;
  }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
.page {{ max-width: 1280px; margin: 0 auto; padding: 32px 16px 64px; }}
.hero h1 {{ font-family: Georgia, "Times New Roman", serif; font-weight: 600; font-size: clamp(28px, 4vw, 42px); margin: 0 0 8px; }}
.hero p {{ margin: 0; color: var(--muted); }}
.request {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }}
.chip {{ background: var(--accent-soft); color: var(--accent); border-radius: 999px; padding: 4px 12px; font-size: 14px; font-weight: 600; }}
.chip.plain {{ background: var(--surface); color: var(--text); border: 1px solid var(--line); font-weight: 500; }}
.route {{ margin-top: 48px; }}
.route header {{ max-width: 760px; }}
.eyebrow {{ text-transform: uppercase; letter-spacing: .12em; font-size: 12px; color: var(--accent); font-weight: 700; margin: 0; }}
.route h2 {{ font-family: Georgia, "Times New Roman", serif; font-size: clamp(24px, 3vw, 32px); margin: 4px 0 8px; }}
.pitch {{ margin: 0 0 8px; font-size: 17px; }}
.meta {{ display: flex; flex-wrap: wrap; gap: 16px; color: var(--muted); font-size: 14px; margin: 0; }}
.timeline {{ list-style: none; padding: 0; margin: 24px 0 0; display: flex; align-items: stretch; gap: 0; overflow-x: auto; padding-bottom: 8px; }}
.step {{ flex: 0 0 280px; display: flex; flex-direction: column; }}
.time {{ font-weight: 700; font-size: 20px; font-variant-numeric: tabular-nums; padding-bottom: 12px; position: relative; }}
.time small {{ font-weight: 500; font-size: 13px; color: var(--muted); margin-left: 6px; }}
.time::after {{ content: ""; position: absolute; left: 0; right: -64px; bottom: 0; height: 2px; background: var(--accent); opacity: .35; }}
.step:last-child .time::after {{ right: 0; }}
.time::before {{ content: ""; position: absolute; left: 0; bottom: -5px; width: 12px; height: 12px; border-radius: 50%; background: var(--accent); }}
.card {{ margin-top: 16px; background: var(--surface); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; display: flex; flex-direction: column; flex: 1; }}
.photo {{ position: relative; aspect-ratio: 16 / 10; overflow: hidden; background: linear-gradient(135deg, var(--accent-soft), var(--line)); }}
.photo img {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; display: block; }}
.role {{ position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,.6); color: #fff; font-size: 12px; font-weight: 600; padding: 3px 10px; border-radius: 999px; }}
.content {{ padding: 14px 16px 16px; display: flex; flex-direction: column; flex: 1; }}
.content h3 {{ margin: 0 0 4px; font-size: 17px; line-height: 1.3; }}
.place {{ margin: 0 0 8px; color: var(--muted); font-size: 14px; }}
.text {{ margin: 0 0 10px; font-size: 14px; }}
.tags {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 10px; }}
.tag {{ font-size: 12px; border: 1px solid var(--line); border-radius: 999px; padding: 1px 8px; color: var(--muted); }}
.tag.asked {{ border-color: var(--accent); color: var(--accent); }}
.tag.word {{ font-style: italic; border-style: dashed; }}
.tag.orig {{ background: var(--walk-soft); color: var(--walk); border-color: transparent; font-weight: 600; }}
.basis {{ font-size: 13px; border-radius: 8px; padding: 6px 10px; margin: 0 0 12px; }}
.basis.ok {{ background: var(--ok-soft); color: var(--ok); }}
.basis.free {{ background: var(--free-soft); color: var(--free); }}
.basis.walk {{ background: var(--walk-soft); color: var(--walk); }}
.foot {{ margin-top: auto; display: flex; align-items: center; justify-content: space-between; gap: 12px; }}
.price {{ font-weight: 700; }}
.book {{ display: inline-block; text-decoration: none; font-weight: 600; font-size: 14px; padding: 8px 16px; border-radius: 999px; border: 1px solid var(--accent); color: var(--accent); }}
.book.primary {{ background: var(--accent); color: #fff; }}
.book:hover {{ filter: brightness(1.08); }}
.source {{ margin: 10px 0 0; font-size: 12px; color: var(--muted); }}
.hop {{ flex: 0 0 64px; align-self: flex-start; margin-top: 44px; display: flex; flex-direction: column; align-items: center; text-align: center;
  font-size: 12px; color: var(--muted); text-decoration: none; padding-top: 40px; line-height: 1.3; }}
.hop span {{ font-size: 18px; }}
.hop:hover {{ color: var(--accent); }}
.empty {{ margin-top: 48px; color: var(--muted); }}
.redo {{ display: none; font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; border-radius: 999px; padding: 4px 12px;
  border: 1px solid var(--accent); background: var(--surface); color: var(--accent); text-transform: none; letter-spacing: 0; }}
.live .redo {{ display: inline-block; }}
.eyebrow .redo {{ margin-left: 12px; vertical-align: middle; }}
.redo.on-photo {{ position: absolute; top: 8px; right: 8px; background: rgba(0,0,0,.6); color: #fff; border-color: transparent; }}
.redo:hover:not(:disabled) {{ filter: brightness(1.1); }}
.redo:disabled {{ opacity: .5; cursor: wait; }}
.redo.busy {{ opacity: 1; }}
.redo:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.flash {{ animation: flash 1.6s ease-out; }}
@keyframes flash {{ from {{ box-shadow: 0 0 0 3px var(--accent); }} to {{ box-shadow: 0 0 0 3px transparent; }} }}
@media (max-width: 720px) {{
  .timeline {{ flex-direction: column; overflow: visible; border-left: 2px solid var(--accent-soft); margin-left: 6px; padding-left: 18px; }}
  .step {{ flex: none; }}
  .time::after {{ display: none; }}
  .time::before {{ left: -25px; bottom: auto; top: 9px; }}
  .hop {{ flex: none; flex-direction: row; gap: 8px; margin: 12px 0; padding: 0; align-self: flex-start; }}
}}
</style>
</head>
<body>
<main class="page" data-page="{name}">
  <section class="hero">
    <h1>{count} soirées pour vous deux</h1>
    <p>Chaque étape est gratuite ou réservable ce soir-là ; les trajets se font à pied quand c'est possible.</p>
    <div class="request">
      <span class="chip plain">{day}</span><span class="chip plain">{hours}</span><span class="chip plain">Budget {budget} à deux</span>{vibes}
    </div>
  </section>
  {body}
</main>
{script}
</body>
</html>
"""

# Served by surprise.quiz, the page redraws a route or a step, then reloads on it.
# Opened as a file, it has no server: the buttons stay hidden.
_SCRIPT = """<script>
(() => {
  const page = document.querySelector("main").dataset.page;
  if (!page || location.protocol === "file:") return;
  document.body.classList.add("live");
  const back = sessionStorage.getItem("redone");
  if (back) {
    sessionStorage.removeItem("redone");
    const target = document.querySelector(back)?.closest(".card, .route");
    if (target) { target.scrollIntoView({ block: "center" }); target.classList.add("flash"); }
  }
  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-redo]");
    if (!button) return;
    const buttons = document.querySelectorAll("[data-redo]");
    const label = button.textContent;
    buttons.forEach((b) => { b.disabled = true; });
    button.classList.add("busy");
    button.textContent = "Recherche…";
    try {
      const response = await fetch(`/api/parcours/${page}/${button.dataset.redo}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
      });
      const answer = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(answer.error || "la recherche a échoué");
      const card = button.closest(".card");
      sessionStorage.setItem("redone", card ? `[data-redo="${button.dataset.redo}"]` : `#${button.closest(".route").id}`);
      location.reload();
    } catch (error) {
      alert(`Pas de nouvelle proposition : ${error.message}`);
      buttons.forEach((b) => { b.disabled = false; });
      button.classList.remove("busy");
      button.textContent = label;
    }
  });
})();
</script>"""


# Command line ---------------------------------------------------------------


@dataclass
class Base:
    """The activities that can be steps, with their originality: loaded once for several evenings."""

    items: list[dict[str, Any]]
    originality: dict[tuple[str, str], int]

    @classmethod
    def load(cls, store: LocalStore) -> "Base":
        items = [item for item in store.list_for_moderation() if item["status"] not in ("rejected", "filtered")]
        scorer = Scorer(items)
        return cls(items, {(i["source_id"], i["external_id"]): scorer.score(i).score for i in items})


def plan(store: LocalStore, request: Request, checks: int = 60, count: int = 3, base: Base | None = None) -> list[Route]:
    return pick(evening_routes(store, base or Base.load(store), request, checks), count)


def evening_routes(store: LocalStore, base: Base, request: Request, checks: int = 60) -> list[Route]:
    """Every route found for the evening, best first."""
    routes = compose(candidates_for(store, base, request, checks), request)
    for route in routes:
        route.request = request
    return routes


def candidates_for(store: LocalStore, base: Base, request: Request, checks: int = 60) -> list[Candidate]:
    """The activities that can be a step that evening, scored."""
    items = base.items
    prescore = {key: quick_score(i, request, base.originality[key]) for i in items if (key := (i["source_id"], i["external_id"]))}
    checked = check_engines(store, items, request, checks, prescore) if checks else store.cached_availability(
        request.day.isoformat(), request.party, CACHE_HOURS
    )
    candidates = []
    for item in items:
        key = (item["source_id"], item["external_id"])
        candidate = build_candidate(item, request, checked.get(key), base.originality[key])
        if candidate:
            candidate.score = score(candidate, request)
            if candidate.score > -math.inf:
                candidates.append(candidate)
    kinds = Counter(c.kind for c in candidates)
    print(
        f"{len(candidates)} étapes possibles ce soir-là : {kinds['seance']} séances, {kinds['verifie']} créneaux vérifiés, "
        f"{kinds['gratuit']} gratuites, {kinds['sans_resa']} sans réservation"
    )
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("days", type=date.fromisoformat, nargs="+", help="date de la soirée, AAAA-MM-JJ (plusieurs : parcours répartis sur ces soirs)")
    parser.add_argument("--budget", type=float, required=True, help="budget approximatif pour deux, en euros")
    parser.add_argument("--de", dest="start", default="19:00", help="début de la soirée (19:00 par défaut)")
    parser.add_argument("--a", dest="end", default="00:30", help="fin de la soirée (00:30 par défaut)")
    parser.add_argument(
        "--vibes", default="romantique",
        help=f"envies séparées par des virgules, parmi : {', '.join(VIBES)}",
    )
    parser.add_argument("--checks", type=int, default=60, help="vérifications de disponibilité en direct au plus (0 : cache seul)")
    parser.add_argument("--parcours", type=int, default=3, help="nombre de parcours proposés (3 par défaut)")
    parser.add_argument(
        "--trame",
        help=f"étapes imposées dans l'ordre, séparées par des virgules : {', '.join(SLOTS)} ou une vibe (ex. apero,insolite,fete)",
    )
    parser.add_argument("--trajet-max", type=int, default=35, help="minutes de trajet au plus entre deux étapes (35 par défaut)")
    parser.add_argument("--strict", action="store_true", help="sans bars ni clubs non réservables")
    parser.add_argument("--db", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--no-claude", action="store_true", help="titres et pitchs par règles, sans Claude")
    parser.add_argument("--no-open", action="store_true", help="ne pas ouvrir la page")
    args = parser.parse_args()
    # A Windows console cannot show every character (✓, ✗): replace them rather than fail.
    sys.stdout.reconfigure(errors="replace")

    vibes = [v.strip() for v in args.vibes.split(",") if v.strip()]
    if unknown := [v for v in vibes if v not in VIBES]:
        parser.error(f"envies inconnues : {', '.join(unknown)} (possibles : {', '.join(VIBES)})")
    trame = [s.strip() for s in (args.trame or "").split(",") if s.strip()]
    if unknown := [s for s in trame if s not in SLOTS and s not in VIBES]:
        parser.error(f"étapes inconnues : {', '.join(unknown)} (possibles : {', '.join([*SLOTS, *VIBES])})")
    days = sorted(set(args.days))
    requests = []
    for day in days:
        begin, finish = window(day, args.start, args.end)
        requests.append(Request(day, args.budget, begin, finish, vibes, walk_in=not args.strict, trame=trame, max_travel=args.trajet_max))

    with LocalStore(args.db) as store:
        routes, path = generate(store, requests, args.parcours, args.checks, claude=not args.no_claude)
    for index, route in enumerate(routes, 1):
        print(f"\n{index}. {_weekday(route.request.day)} {route.request.day:%d/%m} · {route.title} — {route.price:.0f} € à deux")
        for step in route.steps:
            print(f"   {step.start:%H:%M}-{step.end:%H:%M}  {step.candidate.title[:70]}  [{step.basis}]")
    print(f"\nPage : {path.resolve()}")
    if not args.no_open:
        webbrowser.open(path.resolve().as_uri())


def generate(
    store: LocalStore, requests: list[Request], count: int, checks: int = 60, claude: bool = True, name: str | None = None,
) -> tuple[list[Route], Path]:
    """The best routes over the evenings asked, named, and the page showing them."""
    base = Base.load(store)
    routes: list[Route] = []
    for request in requests:
        if len(requests) > 1:
            print(f"\n— {_weekday(request.day)} {request.day:%d/%m}")
        routes += evening_routes(store, base, request, checks)
    # The best routes of all evenings together, without a step in common.
    routes = pick(sorted(routes, key=lambda route: -route.score), count)
    if len(requests) > 1:
        routes.sort(key=lambda route: (route.steps[0].start, -route.score))
    for route in routes:
        name_by_rules(route, route.request)
    if claude:
        name_with_claude(routes, requests[0])
    days = [request.day for request in requests]
    name = name or (days[0].isoformat() if len(days) == 1 else f"{days[0].isoformat()}_{days[-1].isoformat()}")
    state = {"routes": routes, "requests": requests, "seen": {s.candidate.key for r in routes for s in r.steps}}
    return routes, save(name, state)


# Regeneration ----------------------------------------------------------------
# The page's routes are kept next to it (data/parcours/<name>.pkl), so that one route, or one step
# of a route, can be drawn again from the page. Activities already shown are not proposed again
# while others fit.


def save(name: str, state: dict[str, Any]) -> Path:
    """The page and its routes, written under this name."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{name}.pkl").write_bytes(pickle.dumps(state))
    path = OUTPUT_DIR / f"{name}.html"
    requests = state["requests"]
    path.write_text(render(state["routes"], requests[0], [r.day for r in requests], name), encoding="utf-8")
    return path


def load(name: str) -> dict[str, Any] | None:
    path = OUTPUT_DIR / f"{name}.pkl"
    try:
        return pickle.loads(path.read_bytes()) if path.exists() else None
    except (pickle.UnpicklingError, AttributeError, EOFError, TypeError):
        return None  # written by an older version of this module


def regenerate(
    store: LocalStore, base: Base, name: str, index: int, position: int | None = None, checks: int = 10, claude: bool = True,
) -> str | None:
    """Draws route `index` again, or only its step `position`, and rewrites the page; the error, if any."""
    state = load(name)
    if state is None:
        return "parcours introuvable : relancez la composition"
    routes = state["routes"]
    if not 0 <= index < len(routes) or (position is not None and not 0 <= position < len(routes[index].steps)):
        return "étape inconnue"
    route = routes[index]
    request = route.request or state["requests"][0]
    candidates = candidates_for(store, base, request, checks)
    on_page = {s.candidate.key for r in routes for s in r.steps}
    if position is None:
        found = compose([c for c in candidates if c.key not in {s.candidate.key for s in route.steps}], request)
        others = [r for r in routes if r is not route]
        fresh = [r for r in found if not {s.candidate.key for s in r.steps} & state["seen"]]
        chosen = pick(fresh, 1, others) or pick(found, 1, others)
        if not chosen:
            return "aucun autre parcours complet ce soir-là"
        new = chosen[0]
    else:
        steps = replace_step(route, position, candidates, request, state["seen"] | on_page) or replace_step(
            route, position, candidates, request, on_page
        )
        if not steps:
            return "aucune autre activité ne s'enchaîne à cette étape"
        new = Route(steps, _route_score(steps, request))
    new.request = request
    name_by_rules(new, request)
    if claude:
        name_with_claude([new], request)
    routes[index] = new
    state["seen"] |= {s.candidate.key for s in new.steps}
    save(name, state)
    return None

if __name__ == "__main__":
    main()
