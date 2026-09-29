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
import threading
import time as clock
import webbrowser
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from surprise.local_store import LocalStore, open_store
from surprise.originality import Scorer
from surprise.sources import source_name
from surprise.tags import TAGS, VIBES, describe

PARIS = ZoneInfo("Europe/Paris")
OUTPUT_DIR = Path("data/parcours")
CACHE_HOURS = 6
CHECK_WORKERS = 8  # booking engines asked at once
WALK_KM = 1.3  # about 20 minutes on foot
DEFAULT_MODEL = "claude-opus-5-5"

# Minutes an activity lasts when the source does not say.
_DURATIONS = [
    ("restaurant", 105), ("cabaret", 120), ("nuit", 180), ("atelier", 120), ("theatre", 90), ("humour", 80),
    ("concert", 90), ("spectacle", 90), ("croisiere", 75), ("bien_etre", 90), ("jeux", 75), ("visite", 90),
    ("expo", 75), ("musee", 90), ("bar", 75), ("cinema", 110),
]
# Price for two when a walk-in place gives none.
_ESTIMATES = {"repas": 90, "verre": 30, "sortie": 40, "nuit": 220}
# A night's price from Time Out's scale when no price is given ("Prix : €€€").
_NIGHT_SCALE = {1: 120, 2: 180, 3: 300, 4: 550}
NIGHT_TRAVEL = 30  # minutes at most from the evening's last step to the hotel


def night_budget_for(budget: float) -> float:
    """What sleeping out adds to the evening's budget: a room of the evening's standing, 120 to 600 € for two."""
    return float(min(600, max(120, round(budget * 1.5 / 10) * 10)))

CHECK_OUT = time(11)
# When a walk-in place gives no hours: when couples usually go, and until when.
# When a dinner may start: not a table at 23:00 after the show.
DINNER_HOURS = (time(18, 30), time(21, 30))
_USUAL_HOURS = {"verre": (time(18), time(1, 30)), "club": (time(23), time(5))}
_ROMANTIC_TAGS = {"chandelles", "vue", "sur_l_eau", "en_duo", "cache", "chic", "jazz", "classique", "eglise", "dans_le_noir", "gastronomique", "massage"}
_ROMANTIC_WORDS = {"romantique", "intimiste", "cosy", "aux chandelles", "vue panoramique", "coucher de soleil", "en duo"}
_DULL = {"salon", "conference"}
# Plays and stand-up fill every evening (hundreds a night): an ordinary one comes after the unusual, the more so as
# the couple dares; stand-up keeps its place when they asked to laugh.
_PLENTIFUL = {"theatre", "humour"}
_PLENTIFUL_BELOW = 45  # originality from which a play or a comedy club stands out
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
    no_dinner: bool = False  # the couple will have eaten: no meal step (dinner cruises and shows included)
    overnight: bool = False  # the evening ends in a hotel ("découcher")
    night_budget: float | None = None  # euros for the room, added to the evening's budget (night_budget_for by default)

    @property
    def room_budget(self) -> float:
        return self.night_budget if self.night_budget is not None else night_budget_for(self.budget)


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
    night: Step | None = None  # the hotel where the evening ends, when the couple sleeps out

    @property
    def price(self) -> float:
        """The evening's price, the night apart."""
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


_SHOWS = {"concert", "humour", "theatre", "spectacle", "cabaret", "nuit"}
# A place where one can only drink, with a board to share at most: a bar, a wine cellar, tapas, a rooftop.
_DRINKS = re.compile(r"\bbar\b|bar à|\bcaves?\b|planches?|\bap[ée]ro|tapas|\bpub\b|rooftop|speak ?easy")


def role(activity: dict[str, Any], tags: list[str], ate: bool = False) -> str:
    """The step's part: "repas", "verre" or "sortie". When the couple will have eaten (`ate`), a place that also pours drinks is
    a drink, a show with a restaurant is the show; only an offer that is a meal (a dinner cruise) stays one."""
    categories = set(activity.get("categories") or [])
    if "atelier" in categories:
        return "sortie"
    if "restaurant" in categories or "diner" in tags or ("gastronomique" in tags and not categories - {"gastronomie", "restaurant", "bar"}):
        if not ate or "diner" in tags:
            return "repas"
        if categories & _SHOWS:
            return "sortie"
        text = f"{activity.get('title') or ''} {(activity.get('venue') or {}).get('name') or ''}".lower()
        if "bar" in categories or {"vin", "mixologie", "degustation"} & set(tags) or _DRINKS.search(text):
            return "verre"
        return "repas"
    if "bar" in categories and not categories & _SHOWS:
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
    if is_hotel(item):
        return None  # a hotel is where the evening ends (night_for), not a step of it
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
    role_ = role(activity, found["tags"], ate=request.no_dinner)
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
    # A restaurant's wine cellar or rooftop, for a couple who ate, is walked into like a bar.
    walk_in = request.walk_in and role_ != "repas" and (role_ == "verre" or categories & {"bar", "nuit"}) and item["source_id"] not in _PLATFORMS
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
    if request.no_dinner and candidate.role == "repas":
        return -math.inf  # they will have eaten
    if "romantique" in candidate.vibes:
        value += 1.2
    value += min(2, 0.5 * len(_ROMANTIC_TAGS & set(candidate.tags)))
    value += min(1.2, 0.4 * len(_ROMANTIC_WORDS & set(candidate.keywords)))
    if request.prefer & set(candidate.tags):
        value += 1
    # Originality counts more for a daring couple (surprise.originality: offbeat, rare, curated, not a classic).
    value += (candidate.originality - 35) / 25 * (0.5 + request.audace)
    categories = set(activity.get("categories") or [])
    if _DULL & categories:
        value -= 1.5
    if _PLENTIFUL & categories and candidate.originality < _PLENTIFUL_BELOW and not ("rire" in matched and "humour" in categories):
        value -= 0.8 + 1.2 * request.audace
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
    # Half of the checks for dinners, the rarest step to confirm; none when the couple will have eaten.
    dinners = [item for item in todo if role(item["activity"], describe(item["activity"])["tags"], request.no_dinner) == "repas"]
    others = [item for item in todo if item not in dinners]
    taken = 0 if request.no_dinner else min(len(dinners), limit // 2)
    todo = dinners[:taken] + others[: limit - taken]
    if todo:
        print(f"Vérification de {len(todo)} disponibilités (moteurs de réservation)…")

    def one(item: dict[str, Any]) -> tuple[str | None, availability.Availability]:
        try:
            found = availability.check(client, item, request.day, request.party)
        except (httpx.HTTPError, ValueError, KeyError) as error:
            found = "?", availability.Availability(None, detail=f"erreur : {error}"[:200])
        return found or (None, availability.Availability(None, detail="sans moteur pris en charge"))

    # Several activities at once, but each site asked at most every half second, as when checked one by one.
    hooks = {"request": [_paced(availability.DELAY_SECONDS / 2)]}
    with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": availability.USER_AGENT}, event_hooks=hooks) as client, \
            ThreadPoolExecutor(CHECK_WORKERS) as pool:
        futures = {pool.submit(one, item): item for item in todo}
        # Written from this thread only: the store's connection is not shared.
        for index, future in enumerate(as_completed(futures), 1):
            item, (engine, result) = futures[future], future.result()
            store.save_availability(item["source_id"], item["external_id"], day, request.party, engine, result.available, result.slots, result.detail)
            cached[(item["source_id"], item["external_id"])] = {"engine": engine, "available": result.available, "slots": result.slots, "detail": result.detail}
            mark = {True: "✓", False: "✗", None: "·"}[result.available]
            print(f"  {index:>3}/{len(todo)} {mark} {item['activity']['title'][:70]}")
    return cached


def _paced(delay: float) -> Callable[[httpx.Request], None]:
    """An httpx hook that spaces the requests to a same host by `delay` seconds, across threads."""
    lock, next_at = threading.Lock(), {}

    def wait(request: httpx.Request) -> None:
        with lock:
            at = max(clock.monotonic(), next_at.get(request.url.host, 0.0))
            next_at[request.url.host] = at + delay
        clock.sleep(max(0.0, at - clock.monotonic()))

    return wait


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
                if candidate.key in used or candidate.venue.lower() in venues or not _role_fits(candidate, roles, steps, bool(trame), request.overnight):
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


def _role_fits(candidate: Candidate, roles: Counter, steps: list[Step], trame: bool = False, overnight: bool = False) -> bool:
    """Without a trame: three activities at most, four if the evening sleeps out; one dinner, one drink among
    them. Always: no kind of outing twice."""
    if not trame:
        if len(steps) >= (4 if overnight else 3):
            return False
        if candidate.role in ("repas", "verre") and roles[candidate.role]:
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


def _same(title: str) -> str:
    """A title as compared between listings: "Rex Club presents: X" and "REX CLUB PRESENTS – X" are one."""
    return " ".join(re.findall(r"\w+", title.lower()))


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
    # Never the same activity again under another listing (a concert sold on two platforms): not its venue, not its title.
    venues = {s.candidate.venue.lower() for s in steps} - {""}
    titles = {_same(old.candidate.title)}
    budget = request.budget * 1.2 - sum(s.candidate.price for s in others)
    wait = timedelta(minutes=90 if slot == "fete" else 60 if request.trame else 50)
    best, best_value = None, -math.inf
    for candidate in candidates:
        if candidate.key in excluded or candidate.venue.lower() in venues or _same(candidate.title) in titles or candidate.price > budget:
            continue
        if (slot is None and candidate.role != old.candidate.role) or not _role_fits(candidate, roles, others, bool(request.trame), request.overnight):
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


# The night ------------------------------------------------------------------
# A couple who sleeps out ends the evening in a hotel, a love room or a secret room near its last step.


def is_hotel(item: dict[str, Any]) -> bool:
    return "hotel" in (item["activity"].get("categories") or [])


def night_price(activity: dict[str, Any]) -> tuple[float, bool]:
    """A room's price for the night, and whether it is a guess (from Time Out's scale, "Prix : €€€", if given)."""
    price, estimated = price_for_two(activity, "nuit")
    if estimated:
        labels = " ".join(offer.get("label") or "" for offer in activity.get("offers") or [])
        if scale := re.search(r"€{1,4}", labels):
            price = float(_NIGHT_SCALE[len(scale.group(0))])
    return price, estimated


def hotels(base: "Base") -> list[Candidate]:
    """The rooms of the base, as the last step of an evening."""
    found = []
    for item in base.items:
        if not is_hotel(item) or not (place := coordinates(item)):
            continue
        activity, venue = item["activity"], item["activity"].get("venue") or {}
        tags = describe(activity)
        price, estimated = night_price(activity)
        found.append(Candidate(
            item=item, title=activity["title"], venue=venue.get("name") or "", arrondissement=venue.get("arrondissement"),
            lat=place[0], lon=place[1], tags=tags["tags"], vibes=tags["vibes"], role="nuit", duration=0, price=price,
            price_estimated=estimated, starts=[], basis="Chambre à réserver en ligne · disponibilités à vérifier", kind="nuit",
            booking_url=booking_url(item) or str(activity.get("website") or "") or None,
            originality=base.originality[(item["source_id"], item["external_id"])],
        ))
    return found


def night_for(route: Route, rooms: list[Candidate], request: Request, taken: set) -> Step | None:
    """The room where the route ends: close to its last step, within the night's budget (+20 % at most), romantic, unusual."""
    last = route.steps[-1]
    budget = request.room_budget
    best, best_value, best_km = None, -math.inf, 0.0
    for room in rooms:
        if room.key in taken or request.avoid & (set(room.tags) | set(room.item["activity"].get("categories") or [])):
            continue
        if room.price > budget * 1.2:
            continue
        km = distance_km((last.candidate.lat, last.candidate.lon), (room.lat, room.lon))
        if travel_minutes(km) > NIGHT_TRAVEL:
            continue
        value = -0.08 * travel_minutes(km) + room.originality / 25 + 1.5 * len(set(request.vibes) & set(room.vibes))
        value += 1.0 * bool({"spa", "massage", "baignade", "coquin"} & set(room.tags)) - 0.5 * room.price_estimated
        value -= max(0.0, room.price - budget) / 50
        if value > best_value:
            best, best_value, best_km = room, value, km
    if best is None:
        return None
    start = last.end + timedelta(minutes=travel_minutes(best_km))
    morning = start.date() + timedelta(days=1 if start.hour >= 12 else 0)
    return Step(best, start, datetime.combine(morning, CHECK_OUT, tzinfo=start.tzinfo), travel_minutes(best_km), best_km)


def add_nights(routes: list[Route], rooms: list[Candidate]) -> None:
    """A room for each route whose evening sleeps out, not the same one twice."""
    taken: set = set()
    for route in routes:
        if route.request and route.request.overnight:
            route.night = night_for(route, rooms, route.request, taken)
            if route.night:
                taken.add(route.night.candidate.key)


# Names and pitches ----------------------------------------------------------


# Naming by rules: what each step is, in a word, and where the evening happens. Nothing is invented:
# the words come from the tags, the categories and the step's role.
_TAG_WORDS = {
    "escape_game": "escape game", "murder_party": "enquête", "jeu_de_piste": "chasse au trésor", "quiz": "quiz",
    "karaoke": "karaoké", "jeux_de_societe": "jeux de société", "jeu_video": "réalité virtuelle", "mini_golf": "mini-golf",
    "jeu_actif": "jeux d'adresse", "defouloir": "défouloir", "sport": "sport", "stand_up": "stand-up", "theatre": "théâtre",
    "comedie": "comédie", "comedie_musicale": "comédie musicale", "magie": "magie", "cabaret": "cabaret", "drag": "show drag",
    "cirque": "cirque", "danse": "danse", "classique": "concert classique", "jazz": "jazz", "electro": "dancefloor",
    "concert_live": "concert", "art": "art", "photo": "photo", "mode_design": "design", "histoire": "histoire",
    "sciences": "sciences", "immersif": "immersion", "cinema": "cinéma", "lecture": "lecture", "visite_guidee": "balade",
    "animaux": "animaux", "ceramique": "poterie", "peinture_dessin": "peinture", "cuisine": "atelier cuisine",
    "mixologie": "cocktails", "vin": "vins", "artisanat": "atelier", "floral": "fleurs", "parfum_bougie": "parfums",
    "shooting": "shooting photo", "gastronomique": "grande table", "street_food": "street food", "degustation": "dégustation",
    "brunch_gouter": "goûter", "coquin": "moment coquin", "massage": "massage", "spa": "spa", "flottaison": "flottaison", "relaxation": "yoga",
    "baignade": "baignade",
}
_CATEGORY_WORDS = {
    "concert": "concert", "theatre": "théâtre", "humour": "stand-up", "cabaret": "cabaret", "spectacle": "spectacle",
    "danse": "danse", "cinema": "cinéma", "expo": "expo", "musee": "musée", "visite": "balade", "lieu_insolite": "lieu insolite",
    "atelier": "atelier", "gastronomie": "dégustation", "jeux": "jeux", "sensations": "sensations", "bien_etre": "bien-être",
    "croisiere": "croisière", "festival": "festival", "nuit": "dancefloor", "conference": "conférence", "nature": "nature",
}
# The setting, added to the word when the step has it: "dîner sur l'eau", "concert aux chandelles".
_SETTING_WORDS = {"sur_l_eau": "sur l'eau", "chandelles": "aux chandelles", "vue": "avec vue", "dans_le_noir": "dans le noir", "souterrain": "sous terre"}
_PLACES = {
    1: "près du Louvre", 2: "vers la Bourse", 3: "dans le Haut-Marais", 4: "dans le Marais", 5: "au Quartier latin",
    6: "à Saint-Germain", 7: "au pied de la tour Eiffel", 8: "vers les Champs-Élysées", 9: "entre Pigalle et Opéra",
    10: "le long du canal Saint-Martin", 11: "entre Bastille et Oberkampf", 12: "à Bercy", 13: "à la Butte-aux-Cailles",
    14: "à Montparnasse", 15: "à Vaugirard", 16: "à Passy", 17: "aux Batignolles", 18: "à Montmartre",
    19: "aux Buttes-Chaumont", 20: "à Belleville",
}


def step_word(step: Step) -> str:
    """The step in a few words: "cocktails", "dîner sur l'eau", "stand-up"."""
    candidate = step.candidate
    tags = set(candidate.tags)
    categories = candidate.item["activity"].get("categories") or []
    if candidate.role == "repas":
        word = next((_TAG_WORDS[t] for t in ("gastronomique", "street_food") if t in tags), "dîner")
    elif candidate.role == "verre" and "nuit" not in categories:
        # A bar is said by what one does there (cocktails, games, jazz), else by the hour.
        word = next((_TAG_WORDS[t] for t in ("mixologie", "vin", *candidate.tags) if t in tags and t in _TAG_WORDS), None)
        word = word or ("apéro" if 12 < step.start.hour < 21 else "dernier verre")
    else:
        word = next((_TAG_WORDS[t] for t in candidate.tags if t in _TAG_WORDS), None)
        word = word or next((_CATEGORY_WORDS[c] for c in categories if c in _CATEGORY_WORDS), None) or "surprise"
    said = word in ("croisière",) and "sur_l_eau"  # a cruise is on the water already
    setting = next((_SETTING_WORDS[t] for t in _SETTING_WORDS if t in tags and t != said and _SETTING_WORDS[t] not in word), "")
    return f"{word} {setting}".strip()


def _place(route: Route) -> str:
    arrondissements = Counter(s.candidate.arrondissement for s in route.steps if s.candidate.arrondissement)
    return _PLACES.get(arrondissements.most_common(1)[0][0], "à Paris") if arrondissements else "à Paris"


def _listing(words: list[str]) -> str:
    return words[0] if len(words) == 1 else f"{', '.join(words[:-1])} et {words[-1]}"


def _named(step: Step) -> str:
    """The activity as the source names it, with its venue when the title does not say it."""
    title, venue = step.candidate.title.strip().replace("«", "“").replace("»", "”"), (step.candidate.venue or "").strip()
    title = title if len(title) <= 70 else title[:67].rsplit(" ", 1)[0] + "…"
    return f"« {title} »" + (f" ({venue})" if venue and venue.lower() not in title.lower() else "")


def name_by_rules(route: Route, request: Request) -> None:
    """A title that says what the evening is and where ("Apéro, stand-up et dancefloor entre Pigalle et Opéra"),
    and a pitch that tells it step by step, with the walks and the price."""
    words = list(dict.fromkeys(step_word(step) for step in route.steps))
    route.title = f"{_listing(words)} {_place(route)}"
    route.title = route.title[0].upper() + route.title[1:]
    parts = []
    last = len(route.steps) - 1
    for index, step in enumerate(route.steps):
        how = f"{step.travel} min à pied" if step.distance <= WALK_KM else f"{step.travel} min en métro ou taxi"
        dancing = "fete" in step.candidate.vibes or "nuit" in (step.candidate.item["activity"].get("categories") or [])
        if index == 0:
            parts.append(f"À {_hour(step.start)}, {step_word(step)} : {_named(step)}")
        elif index == last and dancing:
            parts.append(f"et la nuit continue, à {how}, avec {_named(step)} jusqu'à {_hour(step.end)}")
        elif index == last:
            parts.append(f"et pour finir, à {how}, {step_word(step)} : {_named(step)}")
        else:
            parts.append(f"puis, à {how}, {step_word(step)} : {_named(step)}")
    rides = [s for s in route.steps[1:] if s.distance > WALK_KM]
    moves = "Tout se fait à pied" if not rides else "Un seul trajet en métro ou taxi" if len(rides) == 1 else "Les trajets se font en métro ou taxi"
    price = f"pour environ {route.price:.0f} € à deux" if route.price else "sans rien dépenser"
    route.pitch = f"{' ; '.join(parts)}. {moves}, {price}."
    if night := route.night:
        how = f"{night.travel} min à pied" if night.distance <= WALK_KM else f"{night.travel} min en taxi"
        cost = f"{'environ ' if night.candidate.price_estimated else 'dès '}{night.candidate.price:.0f} € la nuit"
        route.pitch += f" Puis on découche, à {how} : {_named(night)}, {cost}."


def _hour(moment: datetime) -> str:
    """20 h, 20 h 30, minuit; an end at 02:59 is said 3 h."""
    rounded = moment + timedelta(minutes=(5 - moment.minute % 5) % 5)
    hour = "minuit" if rounded.hour == 0 else f"{rounded.hour} h"
    return hour + (f" {rounded.minute:02d}" if rounded.minute else "")


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


def _image_url(item: dict[str, Any]) -> str | None:
    """The activity's photo, copied locally first when the source forbids showing it elsewhere."""
    image = item["enrichment"].get("image_url") or ((item["activity"].get("image") or {}).get("url"))
    if images.needs_copy(image):
        copy = images.local_copy(image)
        image = f"/images/{copy.name}" if copy else None
    return image


def _booking(c: Candidate, item: dict[str, Any]) -> tuple[str | None, str]:
    """Where to book or see an activity, and what that link is for."""
    if c.kind == "sans_resa":
        return str(item["activity"].get("website") or item.get("source_url") or "") or None, "voir_lieu"
    if c.price == 0:
        return c.booking_url or item.get("source_url") or None, "voir_fiche"
    return c.booking_url or item.get("source_url") or None, "reserver"


def step_json(step: Step, redo: str | None) -> dict[str, Any]:
    """One step of a route, its data reshaped for a client to display however it likes."""
    c, item = step.candidate, step.candidate.item
    link, action = _booking(c, item)
    return {
        "start": step.start.isoformat(), "end": step.end.isoformat(),
        "travel_minutes": step.travel, "distance_km": step.distance,
        "title": c.title, "venue": c.venue, "arrondissement": c.arrondissement,
        "town": (item["activity"].get("venue") or {}).get("town"),
        "lat": c.lat, "lon": c.lon,
        "role": c.role, "kind": c.kind,
        "price": c.price, "price_estimated": c.price_estimated,
        "booking_url": link, "booking_action": action,
        "image_url": _image_url(item),
        "text": item["enrichment"].get("description") or (item.get("lead_text") or "").strip() or None,
        "vibes": c.vibes, "keywords": c.keywords, "originality": c.originality,
        "basis": step.basis,
        "source_id": item["source_id"], "source_name": source_name(item["source_id"]),
        "redo": redo,
    }


def route_json(index: int, route: Route) -> dict[str, Any]:
    """One route (an evening's timeline), its data reshaped for a client to display however it likes."""
    steps = [step_json(step, f"routes/{index}/steps/{position}") for position, step in enumerate(route.steps)]
    return {
        "index": index, "title": route.title, "pitch": route.pitch,
        "day": route.steps[0].start.date().isoformat(),
        "start": route.steps[0].start.isoformat(), "end": route.steps[-1].end.isoformat(),
        "price": route.price, "price_estimated": any(s.candidate.price_estimated for s in route.steps),
        "steps": steps,
        "night": step_json(route.night, None) if route.night else None,
        "redo": f"routes/{index}",
    }


def soiree_json(name: str, state: dict[str, Any]) -> dict[str, Any]:
    """A composed evening (or several), as data: what the client needs to draw it and to ask for a redraw.

    Sent by surprise.quiz in place of a rendered page — see `render()` below, kept for the command line only.
    """
    routes, requests = state["routes"], state["requests"]
    request = requests[0]
    return {
        "name": name,
        "naming": bool(state.get("naming")),  # Claude's titles are still coming; poll GET /api/parcours/<name>
        "days": [r.day.isoformat() for r in requests],
        "start": request.start.isoformat(), "end": request.end.isoformat(),
        "budget": request.budget, "night_budget": request.room_budget if request.overnight else None,
        "vibes": request.vibes, "trame": request.trame,
        "routes": [route_json(index, route) for index, route in enumerate(routes)],
    }


def render(routes: list[Route], request: Request, days: list[date] | None = None, name: str = "", naming: bool = False) -> str:
    """The routes as timelines; with several evenings, each route says its date.

    Command-line only (see `write_page`) — surprise.quiz sends `soiree_json` instead. The page (its
    `name`) offers to draw a route or a step again; while Claude writes the titles (`naming`), it
    waits for them and reloads.
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
        budget=f"{request.budget:.0f} €" + (f" + {request.room_budget:.0f} € la nuit" if request.overnight else ""),
        vibes=vibes,
        body=body,
        name=html.escape(name),
        naming=' data-naming="1"' if naming else "",
        script=_SCRIPT,
    )


def _render_route(index: int, route: Route, asked: list[str], dated: bool = False) -> str:
    steps = []
    for position, step in enumerate(route.steps):
        if position:
            steps.append(_render_hop(route.steps[position - 1].candidate, step))
        steps.append(_render_step(step, asked, f"routes/{index}/steps/{position}"))
    if night := route.night:
        steps.append(_render_hop(route.steps[-1].candidate, night))
        steps.append(_render_step(night, asked))
    total = route.price
    estimated = any(s.candidate.price_estimated for s in route.steps)
    sleep = f'<span>+ {"≈ " if night.candidate.price_estimated else ""}{night.candidate.price:.0f} € la nuit</span>' if night else ""
    day = route.steps[0].start.date().isoformat()
    return f"""
<section class="route" id="parcours-{index + 1}" data-day="{day}">
  <header>
    <p class="eyebrow">Parcours {index + 1}{f" · {_weekday(route.steps[0].start.date())} {route.steps[0].start:%d/%m}" if dated else ""}
      <button type="button" class="redo" data-redo="routes/{index}" title="Composer une autre soirée à la place de celle-ci">↻ Tout le parcours</button></p>
    <h2>{html.escape(route.title)}</h2>
    <p class="pitch">{html.escape(route.pitch)}</p>
    <p class="meta"><span>{route.steps[0].start:%H:%M} → {route.steps[-1].end:%H:%M}</span>
      <span>{'≈ ' if estimated else ''}{total:.0f} € pour deux</span>{sleep}
      <span>{len(route.steps)} étapes</span></p>
  </header>
  <ol class="timeline">{''.join(steps)}</ol>
  <p class="choose-row"><button type="button" class="choose" data-choose="{index}">✓ On a choisi cette soirée</button></p>
</section>"""


def _render_hop(previous: Candidate, step: Step) -> str:
    """The way from one step to the next, opened in Google Maps."""
    mode = "walking" if step.distance <= WALK_KM else "transit"
    maps = "https://www.google.com/maps/dir/?" + urlencode(
        {"api": 1, "origin": f"{previous.lat},{previous.lon}", "destination": f"{step.candidate.lat},{step.candidate.lon}", "travelmode": mode}
    )
    icon = "🚶" if mode == "walking" else "🚇"
    label = f"{step.travel} min" + (f" · {step.distance * 1000:.0f} m" if step.distance < 1 else f" · {step.distance:.1f} km")
    return f'<a class="hop" href="{html.escape(maps)}" target="_blank" rel="noopener"><span>{icon}</span>{label}</a>'


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
    if c.kind == "nuit":
        price = f"{'≈ ' if c.price_estimated else 'dès '}{c.price:.0f} € la nuit"
    badge = {"verifie": "ok", "seance": "ok", "gratuit": "free", "sans_resa": "walk", "nuit": "walk"}[c.kind]
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
    town = (c.item["activity"].get("venue") or {}).get("town")
    where = f"Paris {c.arrondissement}ᵉ" if c.arrondissement else town if town and town != "Paris" else None
    place = " · ".join(filter(None, [c.venue, where]))
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
_ROLE_LABELS = {"repas": "Dîner", "verre": "Un verre", "sortie": "Sortie", "nuit": "La nuit"}


def _weekday(day: date) -> str:
    return ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"][day.weekday()]


_PAGE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@600;700&family=Space+Grotesk:wght@400;500;600&display=swap" rel="stylesheet">
<script src="/account.js"></script>
<style>
:root {{
  --bg: #fbf3e7; --surface: #ffffff; --text: #211a2b; --muted: #6f6579; --line: #e8dcf3;
  --accent: #ff5c72; --accent-soft: #ffe1e6; --accent-text: #211a2b; --accent-ink: #d6314c;
  --gold: #caa15a; --night-bg: #241a1f; --night-line: #3a2a1f;
  --ok: #1e7a4c; --ok-soft: #e3f3ea; --walk: #8a5a00; --walk-soft: #fbf0d9;
  --free: #1f5fa8; --free-soft: #e2edf9;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #1c1620; --surface: #241c26; --text: #f3ecea; --muted: #b3a7a4; --line: #3a3033;
    --accent: #ff5c72; --accent-soft: #4a2028; --accent-text: #211a2b; --accent-ink: #ff5c72;
    --ok: #6fd3a0; --ok-soft: #1b3226; --walk: #f0c46b; --walk-soft: #372b14;
    --free: #8fbef3; --free-soft: #1a2a3d;
  }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 16px/1.5 "Space Grotesk", system-ui, sans-serif; }}
.page {{ max-width: 1280px; margin: 0 auto; padding: 32px 16px 64px; }}
.banner {{ display: block; width: 100%; height: clamp(140px, 22vw, 240px); object-fit: cover; border-radius: 20px;
  background: var(--line); margin: 0 0 24px; }}
.hero h1 {{ font-family: "Fredoka", sans-serif; font-weight: 600; font-size: clamp(28px, 4vw, 42px); margin: 0 0 8px; }}
.hero p {{ margin: 0; color: var(--muted); }}
.request {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }}
.chip {{ background: var(--accent-soft); color: var(--accent-ink); border-radius: 999px; padding: 4px 12px; font-size: 14px; font-weight: 600; }}
.chip.plain {{ background: var(--surface); color: var(--text); border: 1px solid var(--line); font-weight: 500; }}
.route {{ margin-top: 48px; }}
.route header {{ max-width: 760px; }}
.eyebrow {{ text-transform: uppercase; letter-spacing: .12em; font-size: 12px; color: var(--accent-ink); font-weight: 700; margin: 0; }}
.route h2 {{ font-family: "Fredoka", sans-serif; font-weight: 600; font-size: clamp(24px, 3vw, 32px); margin: 4px 0 8px; }}
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
.tag.asked {{ border-color: var(--accent-ink); color: var(--accent-ink); }}
.tag.word {{ font-style: italic; border-style: dashed; }}
.tag.orig {{ background: var(--walk-soft); color: var(--walk); border-color: transparent; font-weight: 600; }}
.basis {{ font-size: 13px; border-radius: 8px; padding: 6px 10px; margin: 0 0 12px; }}
.basis.ok {{ background: var(--ok-soft); color: var(--ok); }}
.basis.free {{ background: var(--free-soft); color: var(--free); }}
.basis.walk {{ background: var(--walk-soft); color: var(--walk); }}
.foot {{ margin-top: auto; display: flex; align-items: center; justify-content: space-between; gap: 12px; }}
.price {{ font-weight: 700; }}
.book {{ display: inline-block; text-decoration: none; font-weight: 600; font-size: 14px; padding: 8px 16px; border-radius: 999px; border: 1px solid var(--accent-ink); color: var(--accent-ink); }}
.book.primary {{ background: var(--accent); border-color: var(--accent); color: var(--accent-text); }}
.book:hover {{ filter: brightness(1.08); }}
.source {{ margin: 10px 0 0; font-size: 12px; color: var(--muted); }}
.hop {{ flex: 0 0 64px; align-self: flex-start; margin-top: 44px; display: flex; flex-direction: column; align-items: center; text-align: center;
  font-size: 12px; color: var(--muted); text-decoration: none; padding-top: 40px; line-height: 1.3; }}
.hop span {{ font-size: 18px; }}
.hop:hover {{ color: var(--accent-ink); }}
.empty {{ margin-top: 48px; color: var(--muted); }}
.redo {{ display: none; font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; border-radius: 999px; padding: 4px 12px;
  border: 1px solid var(--accent-ink); background: var(--surface); color: var(--accent-ink); text-transform: none; letter-spacing: 0; }}
.live .redo {{ display: inline-block; }}
.eyebrow .redo {{ margin-left: 12px; vertical-align: middle; }}
.redo.on-photo {{ position: absolute; top: 8px; right: 8px; background: rgba(0,0,0,.6); color: #fff; border-color: transparent; }}
.redo:hover:not(:disabled) {{ filter: brightness(1.1); }}
.redo:disabled {{ opacity: .5; cursor: wait; }}
.redo.busy {{ opacity: 1; }}
.redo:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.choose-row {{ margin: 18px 0 0; }}
.choose {{ font: inherit; font-weight: 600; font-size: 14px; cursor: pointer; border-radius: 999px; padding: 10px 20px;
  border: 1px solid var(--accent); background: var(--surface); color: var(--accent-ink); }}
.choose:hover:not(:disabled) {{ background: var(--accent-soft); }}
.choose:disabled {{ cursor: default; opacity: .8; }}
.choose.chosen {{ background: var(--accent); border-color: var(--accent); color: var(--accent-text); }}
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
<main class="page" data-page="{name}"{naming}>
  <img class="banner" src="https://images.unsplash.com/photo-1759503166788-cbe7c2503e96?auto=format&fit=crop&w=1600&q=60" alt="" loading="lazy" decoding="async">
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
  const main = document.querySelector("main");
  const page = main.dataset.page;
  if (!page || location.protocol === "file:") return;
  document.body.classList.add("live");
  // Claude's titles come a few seconds after the page: it reloads on them, a minute at most.
  if (main.dataset.naming) {
    const since = Date.now();
    const wait = async () => {
      const text = await fetch(location.href, { cache: "no-store" }).then((r) => r.text()).catch(() => "");
      if (text && !/<main[^>]*data-naming/.test(text)) return location.reload();
      if (Date.now() - since < 60000) setTimeout(wait, 2000);
    };
    setTimeout(wait, 2000);
  }
  const back = sessionStorage.getItem("redone");
  if (back) {
    sessionStorage.removeItem("redone");
    const target = document.querySelector(back)?.closest(".card, .route");
    if (target) { target.scrollIntoView({ block: "center" }); target.classList.add("flash"); }
  }
  document.addEventListener("click", async (event) => {
    const redo = event.target.closest("[data-redo]");
    if (redo) {
      const buttons = document.querySelectorAll("[data-redo]");
      const label = redo.textContent;
      buttons.forEach((b) => { b.disabled = true; });
      redo.classList.add("busy");
      redo.textContent = "Recherche…";
      try {
        const response = await fetch(`/api/parcours/${page}/${redo.dataset.redo}`, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
        });
        const answer = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(answer.error || "la recherche a échoué");
        const card = redo.closest(".card");
        sessionStorage.setItem("redone", card ? `[data-redo="${redo.dataset.redo}"]` : `#${redo.closest(".route").id}`);
        location.reload();
      } catch (error) {
        alert(`Pas de nouvelle proposition : ${error.message}`);
        buttons.forEach((b) => { b.disabled = false; });
        redo.classList.remove("busy");
        redo.textContent = label;
      }
      return;
    }
    const choose = event.target.closest("[data-choose]");
    if (choose) {
      if (!currentUser()) {
        if (confirm("Connectez-vous pour garder cette soirée dans votre historique. Aller à votre compte ?")) location.href = "/compte";
        return;
      }
      const route = choose.closest(".route");
      const label = choose.textContent;
      choose.disabled = true;
      choose.textContent = "Ajout…";
      try {
        await chooseEvening({
          pageName: page, routeIndex: Number(choose.dataset.choose),
          title: route.querySelector("h2").textContent, pitch: route.querySelector(".pitch").textContent,
          vibes: [...document.querySelectorAll(".request .chip:not(.plain)")].map((c) => c.textContent),
          day: route.dataset.day || null,
        });
        choose.classList.add("chosen");
        choose.textContent = "✓ Choisie, dans votre historique";
      } catch (error) {
        alert(`Impossible de la garder : ${error.message}`);
        choose.disabled = false;
        choose.textContent = label;
      }
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
    parser.add_argument("--decoucher", action="store_true", help="finir la soirée dans un hôtel ou une love room près de la dernière étape")
    parser.add_argument("--budget-nuit", type=float, help="budget de la chambre pour deux, ajouté à --budget (1,5 fois --budget par défaut, 120 à 600 €)")
    parser.add_argument("--strict", action="store_true", help="sans bars ni clubs non réservables")
    parser.add_argument("--db", help="base SQLite ou URL postgresql:// (défaut : SUPABASE_DB_URL, sinon data/surprise.db)")
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
        requests.append(Request(
            day, args.budget, begin, finish, vibes, walk_in=not args.strict, trame=trame, max_travel=args.trajet_max, overnight=args.decoucher,
            night_budget=args.budget_nuit,
        ))

    with open_store(args.db) as store:
        routes, name = generate(store, requests, args.parcours, args.checks, claude=not args.no_claude)
    for index, route in enumerate(routes, 1):
        print(f"\n{index}. {_weekday(route.request.day)} {route.request.day:%d/%m} · {route.title} — {route.price:.0f} € à deux")
        for step in route.steps:
            print(f"   {step.start:%H:%M}-{step.end:%H:%M}  {step.candidate.title[:70]}  [{step.basis}]")
        if night := route.night:
            price = f"{'≈ ' if night.candidate.price_estimated else 'dès '}{night.candidate.price:.0f} €"
            print(f"   {night.start:%H:%M}-{night.end:%H:%M}  nuit : {night.candidate.title[:60]}  [{price}, {night.travel} min]")
    path = write_page(name)
    print(f"\nPage : {path.resolve()}")
    if not args.no_open:
        webbrowser.open(path.resolve().as_uri())


def generate(
    store: LocalStore, requests: list[Request], count: int, checks: int = 60, claude: bool = True, name: str | None = None,
    base: Base | None = None, name_later: bool = False,
) -> tuple[list[Route], str]:
    """The best routes over the evenings asked, named, and the name they are saved under (see `soiree_json`).

    `base`: the activities already loaded (a server keeps them). `name_later`: routes are saved at
    once, named by rules, and Claude's titles replace them when they come (`soiree_json`'s `naming`).
    """
    base = base or Base.load(store)
    routes: list[Route] = []
    for request in requests:
        if len(requests) > 1:
            print(f"\n— {_weekday(request.day)} {request.day:%d/%m}")
        routes += evening_routes(store, base, request, checks)
    # The best routes of all evenings together, without a step in common.
    routes = pick(sorted(routes, key=lambda route: -route.score), count)
    if len(requests) > 1:
        routes.sort(key=lambda route: (route.steps[0].start, -route.score))
    if any(request.overnight for request in requests):
        add_nights(routes, hotels(base))
    for route in routes:
        name_by_rules(route, route.request)
    later = claude and name_later and bool(routes) and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if claude and not later:
        name_with_claude(routes, requests[0])
    days = [request.day for request in requests]
    name = name or (days[0].isoformat() if len(days) == 1 else f"{days[0].isoformat()}_{days[-1].isoformat()}")
    state = {"routes": routes, "requests": requests, "seen": {s.candidate.key for r in routes for s in r.steps}, "naming": int(later)}
    with _SAVING:
        save(name, state)
    if later:
        threading.Thread(target=_name_later, args=(name, routes, requests[0]), daemon=True).start()
    return routes, name


def _route_key(route: Route) -> tuple:
    return tuple((step.candidate.key, step.start) for step in route.steps)


def _name_later(name: str, routes: list[Route], request: Request) -> None:
    """Claude's titles into the saved page, for the routes still on it (one may have been redrawn meanwhile)."""
    try:
        name_with_claude(routes, request)
    finally:
        titles = {_route_key(route): (route.title, route.pitch) for route in routes}
        with _SAVING:
            state = load(name)
            if state is not None:
                for route in state["routes"]:
                    route.title, route.pitch = titles.get(_route_key(route), (route.title, route.pitch))
                state["naming"] = max(0, int(state.get("naming") or 0) - 1)  # titles still awaited for other routes
                save(name, state)


# Regeneration ----------------------------------------------------------------
# The page's routes are kept next to it (data/parcours/<name>.pkl), so that one route, or one step
# of a route, can be drawn again from the page. Activities already shown are not proposed again
# while others fit.


# A page is loaded, changed and saved again by the composition, a redraw and Claude's titles: one at a time.
_SAVING = threading.RLock()


def save(name: str, state: dict[str, Any]) -> None:
    """The routes and requests behind a composed evening, kept under this name so a route or a
    step of it can be drawn again (see `regenerate`) — not a page: surprise.quiz sends JSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{name}.pkl").write_bytes(pickle.dumps(state))


def write_page(name: str) -> Path:
    """The routes saved under `name`, as a page — command-line only, see `render`."""
    state = load(name)
    requests = state["requests"]
    path = OUTPUT_DIR / f"{name}.html"
    path.write_text(render(state["routes"], requests[0], [r.day for r in requests], name, bool(state.get("naming"))), encoding="utf-8")
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
    with _SAVING:
        return _regenerate(store, base, name, index, position, checks, claude)


def _regenerate(store: LocalStore, base: Base, name: str, index: int, position: int | None, checks: int, claude: bool) -> str | None:
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
        # None of the route's activities again, under the same listing or another one.
        keys, titles = {s.candidate.key for s in route.steps}, {_same(s.candidate.title) for s in route.steps}
        venues = {s.candidate.venue.lower() for s in route.steps} - {""}
        found = compose([c for c in candidates if c.key not in keys and _same(c.title) not in titles and c.venue.lower() not in venues], request)
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
    if request.overnight:
        # Its room again if it still fits, else another one than the other routes'.
        others = {r.night.candidate.key for r in routes if r is not route and getattr(r, "night", None)}
        new.night = night_for(new, hotels(base), request, others)
    name_by_rules(new, request)
    later = claude and bool(os.environ.get("ANTHROPIC_API_KEY"))
    routes[index] = new
    state["seen"] |= {s.candidate.key for s in new.steps}
    state["naming"] = int(state.get("naming") or 0) + later
    save(name, state)
    if later:
        threading.Thread(target=_name_later, args=(name, [new], request), daemon=True).start()
    return None

if __name__ == "__main__":
    main()
