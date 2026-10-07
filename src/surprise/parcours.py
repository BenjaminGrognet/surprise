"""Evening routes: three different evenings for a couple, or a band of friends, from a date, a budget, hours and vibes.

Two formulas: Secret Date, for two, and Secret Squad, for a band of friends (2 to 10, a hen or stag party, a
birthday, a friend's night out…), where the romance gives way to what a group shares (games, quizzes, karaoke, dancing) and every price
counts each of them.

Every step of a route is free or bookable that evening, checked as far as the
sources allow:
- a dated show that evening (concerts.paris sessions, Que Faire à Paris,
  Shotgun, Eventbrite…), bookable through its ticketing link or free;
- a slot confirmed live on the booking engine (Funbooker, Wecandoo, Come to
  Paris, Zenchef, SevenRooms, 4escape), for the party, cached a few hours;
- a free place open at that time (opening hours known);
- a bar or club open at that time, walked into without booking (kept on
  purpose in the base), marked as such; --strict leaves them out. A dinner
  always has a table confirmed by the restaurant's booking engine.
Runs whose evenings are unknown (a play "until December") are left out.

The steps are chained in time and space: each one starts after the previous one
ends plus the walk or ride between them, without a long wait. Routes are built
by a beam search that favours the asked vibes, romance (or conviviality) and originality, fills
the evening, keeps to the budget and walks rather than rides. Three routes are
kept, with no activity nor venue in common. Claude names them and writes their
pitch when ANTHROPIC_API_KEY is set; otherwise they are named by rules.

The routes are saved (pipeline.soirees) and shown by the app (app/, /soiree?soiree=<name>).
"""

import argparse
import contextlib
import hashlib
import json
import math
import os
import random
import re
import secrets
import sys
import threading
import time as clock
import unicodedata
import webbrowser
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, fields, is_dataclass, replace
from datetime import date, datetime, time, timedelta
from functools import cached_property
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from surprise import availability, genres, images
from surprise.collectors import come_to_paris, funbooker, wecandoo
from surprise.collectors.facts import BROWSER_HEADERS
from surprise.local_store import LocalStore, open_store
from surprise.originality import Scorer
from surprise.sources import source_name
from surprise.tags import TAGS, VIBES, describe

PARIS = ZoneInfo("Europe/Paris")
# Where composed evenings are kept (table soirees): SUPABASE_DB_URL, else data/surprise.db; surprise.quiz sets its --db.
DB: Path | str | None = None
CACHE_HOURS = 6
CHECK_WORKERS = 8  # booking engines asked at once
# Checks per engine and evening: an engine's site is asked every half second, so its checks follow each other;
# spread over the engines, they run side by side. Come to Paris asks its site 3 or 4 times a check.
PER_ENGINE = 5
_PER_ENGINE_OF = {"come_to_paris": 2}
# Rounds of live checks a redraw may take when every activity kept was proposed already, each one asking the
# engines for activities not yet checked that evening.
SEARCH_ROUNDS = 3
WALK_KM = 1.3  # about 20 minutes on foot
DEFAULT_MODEL = "claude-opus-5-5"

# Minutes an activity lasts when the source does not say.
_DURATIONS = [
    ("restaurant", 105), ("cabaret", 120), ("nuit", 180), ("atelier", 120), ("theatre", 90), ("humour", 80),
    ("concert", 90), ("spectacle", 90), ("croisiere", 75), ("bien_etre", 90), ("jeux", 75), ("visite", 90),
    ("expo", 75), ("musee", 90), ("bar", 75), ("cinema", 110),
]
# Price for two when a walk-in place gives none (a party pays its share of it per head).
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
# A band of friends (Secret Squad): what a group shares counts where romance counts for two.
_CONVIVIAL_TAGS = {
    "quiz", "karaoke", "escape_game", "murder_party", "jeu_de_piste", "jeux_de_societe", "jeu_actif", "mini_golf", "defouloir",
    "jeu_video", "stand_up", "danse", "electro", "cabaret", "drag", "street_food", "degustation", "mixologie", "evjf",
}
_CONVIVIAL_VIBES = {"rire", "defi", "fete"}
# Said in its title, an offer for two (a couple's massage, a love room): never a band's.
_FOR_TWO = re.compile(r"\bduo\b|à deux|\bcouples?\b|amoureux|saint[- ]valentin|love ?room|en tête[- ]à[- ]tête", re.IGNORECASE)
# From this many, a bar or club walked into without booking is a gamble: the band may stand at the door.
WALK_IN_PARTY = 6
_DULL = {"salon", "conference"}
# Plays and stand-up fill every evening (hundreds a night): an ordinary one comes after the unusual, the more so as
# the couple dares; stand-up keeps its place when they asked to laugh.
_PLENTIFUL = {"theatre", "humour"}
_PLENTIFUL_BELOW = 45  # originality from which a play or a comedy club stands out
_CHECKED_SOURCES = {funbooker.SOURCE_ID, come_to_paris.SOURCE_ID, wecandoo.SOURCE_ID}
_PLATFORMS = _CHECKED_SOURCES | {"getyourguide", "tiqets", "civitatis", "explore_paris", "fever", "paris_jetaime_billetterie", "eventbrite", "shotgun", "billetreduc"}
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
    budget: float  # euros for the whole party (two, or the band)
    start: datetime
    end: datetime
    vibes: list[str]
    party: int = 2  # how many go out: two, or the band of a Secret Squad
    formule: str = "duo"  # "duo" (Secret Date, a couple) or "squad" (Secret Squad, a band of friends)
    walk_in: bool = True  # bars and clubs without booking may be steps
    trame: list[str] = field(default_factory=list)  # the steps asked, in order ("apero", "insolite", "fete")
    max_travel: int = 35  # minutes between two steps
    audace: float = 0.5  # 0: classics are fine, 1: only the unusual (questionnaire)
    avoid: set[str] = field(default_factory=set)  # tags, keywords or categories the couple refuses ("dans_le_noir", "sensations")
    prefer: set[str] = field(default_factory=set)  # tags the couple likes ("jazz", "chandelles")
    genres: set[str] = field(default_factory=set)  # the music they like (surprise.genres): concerts keep to it
    dinner: bool = False  # the couple wants a sit-down dinner in the evening
    no_dinner: bool = False  # the couple will have eaten: no meal step (dinner cruises and shows included)
    overnight: bool = False  # the evening ends in a hotel ("découcher")
    night_budget: float | None = None  # euros for the room, added to the evening's budget (night_budget_for by default)
    done: set[tuple[str, str]] = field(default_factory=set)  # activities of evenings the couple chose: never again
    tastes: dict[str, float] = field(default_factory=dict)  # the couple's votes by kind of outing (tastes_from): + liked, − not for them

    @property
    def squad(self) -> bool:
        return self.formule == "squad"

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
    price: float  # for the whole party (price_for)
    price_estimated: bool
    starts: list[datetime]
    basis: str  # why it is bookable that evening
    kind: str  # "verifie", "seance", "gratuit", "sans_resa"
    booking_url: str | None
    ends: dict[datetime, datetime] = field(default_factory=dict)  # known end of a session
    flexible: bool = False  # walk-in: can leave earlier to fit the evening
    originality: int = 35  # surprise.originality, 0-100
    keywords: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)  # what it plays (surprise.genres)
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


def price_for(activity: dict[str, Any], role_: str, party: int = 2) -> tuple[float, bool]:
    """Cheapest price for the party (two, or a band), and whether it is a guess: a price per person counts each of
    them, a couple's every two, a group's once."""
    offers = activity.get("offers") or []
    if any(offer.get("is_free") for offer in offers):
        return 0.0, False
    times = {"per_couple": math.ceil(party / 2), "per_group": 1}
    prices = [
        float(offer["price_min"]) * times.get(offer.get("price_unit"), party)
        for offer in offers
        if offer.get("price_min") is not None
    ]
    if prices and min(prices) > 0:
        return min(prices), False
    return float(_ESTIMATES[role_]) * party / 2, True


def booking_url(item: dict[str, Any]) -> str | None:
    links = [offer.get("booking_url") for offer in item["activity"].get("offers") or []]
    return next(filter(None, links), None) or item["enrichment"].get("booking_url")


def coordinates(item: dict[str, Any]) -> tuple[float, float] | None:
    venue = item["activity"].get("venue") or {}
    lat = venue.get("latitude") or item["enrichment"].get("latitude")
    lon = venue.get("longitude") or item["enrichment"].get("longitude")
    return (float(lat), float(lon)) if lat and lon else None


def needs_check(item: dict[str, Any]) -> bool:
    """An activity without dated sessions whose engine answers for a date: a slot to check, as found at collection."""
    activity = item["activity"]
    return not activity.get("occurrences") and bool((activity.get("booking") or {}).get("check"))


def build_candidate(item: dict[str, Any], request: Request, checked: dict[str, Any] | None, originality: int = 35) -> Candidate | None:
    """The activity as a step of the evening, with its possible start times, or None if it cannot be one.

    A stag or hen party offer is only a band's, an offer for two (said in its title) only a couple's, and an activity
    that says how many it takes (an escape room for 3 to 6) is proposed to as many; a dinner sits down between 18:30
    and 21:30.
    """
    activity = item["activity"]
    if not fits_party(activity, request):
        return None
    if is_hotel(item):
        return None  # a hotel is where the evening ends (night_for), not a step of it
    candidate = _build_candidate(item, request, checked, originality)
    if candidate and candidate.role == "repas":
        candidate.starts = [s for s in candidate.starts if DINNER_HOURS[0] <= s.time() <= DINNER_HOURS[1] and s.date() == request.day]
        if not candidate.starts:
            return None
    if candidate:
        candidate.genres = item_genres(item)
    return candidate


def fits_party(activity: dict[str, Any], request: Request) -> bool:
    """The activity is for this party: a couple's or a band's offer for the formula asked, and its number of players."""
    tags = describe(activity)["tags"]
    if "evjf" in tags and not request.squad:
        return False
    if request.squad and _FOR_TWO.search(activity["title"]):
        return False
    return (activity.get("players_min") or 1) <= request.party <= (activity.get("players_max") or request.party)


def item_genres(item: dict[str, Any]) -> list[str]:
    """What the activity plays (surprise.genres), read in its texts once per loaded activity: only for a candidate,
    as reading the long texts of the whole base took most of a composition."""
    if "genres" not in item:
        item["genres"] = genres.genres(item)
    return item["genres"]


def _build_candidate(item: dict[str, Any], request: Request, checked: dict[str, Any] | None, originality: int) -> Candidate | None:
    activity = item["activity"]
    place = coordinates(item)
    if not place:
        return None
    found = describe(activity)
    role_ = role(activity, found["tags"], ate=request.no_dinner)
    duration = default_duration(activity, role_)
    price, estimated = price_for(activity, role_, request.party)
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
        return Candidate(**base, starts=sorted(set(starts)), ends=ends, basis=f"libre pour {request.party}, vérifié sur {engine}{detail}", kind="verifie")

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


# The couple's votes on the steps they were proposed (app: « on aime ce genre », « pas pour nous »), by kind of outing.
TASTE_UP = 1.0  # score gained per vote for one of the activity's kinds, up to TASTE_MAX
TASTE_MAX = 2.5
TASTE_DOWN = 2.0  # score lost per vote against, down to -TASTE_MIN: a "no" weighs more than a "yes"
TASTE_MIN = 5.0
VOTED_OUT = -2  # votes against an activity's kinds (net) from which it is never proposed


def kinds(item: dict[str, Any], tags: list[str] | None = None) -> set[str]:
    """What kind of outing an activity is, for the couple's votes: its activity tags ("escape_game", "jazz"), else its
    categories ("bar", "humour"). `tags`: the activity's, when already read."""
    tags = describe(item["activity"])["tags"] if tags is None else tags
    return {t for t in tags if TAGS[t]["facet"] == "activite"} or set(item["activity"].get("categories") or [])


def tastes_from(base: "Base", votes: dict[tuple[str, str], int]) -> dict[str, float]:
    """The kinds of outing the couple voted for (+) or against (−), from the activities they voted on (+1 or -1 each);
    an activity that left the base since is not counted."""
    weights: Counter = Counter()
    for key, vote in votes.items():
        if (item := base.by_key.get(key)) is not None:
            for kind in kinds(item):
                weights[kind] += vote
    return {kind: weight for kind, weight in weights.items() if weight}


def taste(found: set[str], request: Request) -> float:
    """What the couple's votes say of an activity of these kinds: a bonus, a malus, or -inf once voted out."""
    total = sum(request.tastes.get(kind, 0) for kind in found)
    if total <= VOTED_OUT:
        return -math.inf
    return min(TASTE_MAX, TASTE_UP * total) if total > 0 else max(-TASTE_MIN, TASTE_DOWN * total)


def affinity(tags: list[str], vibes: list[str], keywords: list[str], request: Request) -> float:
    """What makes an outing theirs beyond the wishes: romance for two, what a band shares (games, karaoke, dancing)."""
    if request.squad:
        return 1.2 * bool(_CONVIVIAL_VIBES & set(vibes)) + min(2, 0.5 * len(_CONVIVIAL_TAGS & set(tags)))
    value = 1.2 * ("romantique" in vibes)
    value += min(2, 0.5 * len(_ROMANTIC_TAGS & set(tags)))
    return value + min(1.2, 0.4 * len(_ROMANTIC_WORDS & set(keywords)))


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
    value += taste(kinds(item, candidate.tags), request)
    if value == -math.inf:
        return -math.inf  # a kind of outing they voted out
    if request.no_dinner and candidate.role == "repas":
        return -math.inf  # they will have eaten
    if candidate.role == "sortie" and genres.off_key(candidate.genres, set(activity.get("categories") or []), request.genres):
        return -math.inf  # not their music
    value += affinity(candidate.tags, candidate.vibes, candidate.keywords, request)
    if request.prefer & set(candidate.tags) or request.genres & set(candidate.genres):
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
    value += {"verifie": 0.6, "seance": 0.4, "gratuit": 0.2, "sans_resa": -0.3 if request.party < WALK_IN_PARTY else -1.5}[candidate.kind]
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
    todo = _spread(sorted(
        (
            item for item in items
            if needs_check(item) and (key := (item["source_id"], item["external_id"])) not in cached and prescore.get(key, 0) > -math.inf
        ),
        key=lambda item: -prescore.get((item["source_id"], item["external_id"]), 0),
    ))
    # Half of the checks for dinners at least, the rarest step to confirm (all of them when dinners alone are asked);
    # none when the couple will have eaten.
    dinners = [item for item in todo if role(item["activity"], describe(item["activity"])["tags"], request.no_dinner) == "repas"]
    others = [item for item in todo if item not in dinners]
    taken = 0 if request.no_dinner else min(len(dinners), max(limit // 2, limit - len(others)))
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
        answers = []
        try:
            for index, future in enumerate(as_completed(futures), 1):
                item, (engine, result) = futures[future], future.result()
                answers.append((item["source_id"], item["external_id"], day, request.party, engine, result.available, result.slots, result.detail))
                cached[(item["source_id"], item["external_id"])] = {"engine": engine, "available": result.available, "slots": result.slots, "detail": result.detail}
                mark = {True: "✓", False: "✗", None: "·"}[result.available]
                print(f"  {index:>3}/{len(todo)} {mark} {item['activity']['title'][:70]}")
        finally:
            # In one write, from this thread only: the store's connection is not shared.
            store.save_availabilities(answers)
    return cached


def _spread(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The first items of each engine (their booking's check), in their order: PER_ENGINE, or the engine's own."""
    asked: Counter = Counter()
    kept = []
    for item in items:
        engine = item["activity"]["booking"]["check"].split(":", 1)[0]
        asked[engine] += 1
        if asked[engine] <= _PER_ENGINE_OF.get(engine, PER_ENGINE):
            kept.append(item)
    return kept


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
    """Ranking before any check: vibes, romance (a band: conviviality), originality and a photo; never one not for
    this party, not to spend a live check on it."""
    if not fits_party(item["activity"], request):
        return -math.inf
    found = describe(item["activity"])
    asked = set(request.vibes)
    value = 4 * len(asked & set(found["vibes"])) / len(asked) if asked else 1
    if request.squad:
        value += 1.2 * bool(_CONVIVIAL_VIBES & set(found["vibes"])) + 0.5 * len(_CONVIVIAL_TAGS & set(found["tags"]))
    else:
        value += 1.2 * ("romantique" in found["vibes"]) + 0.5 * len(_ROMANTIC_TAGS & set(found["tags"]))
    value += 0.6 * bool(item["enrichment"].get("image_url") or item["activity"].get("image"))
    value += (originality - 35) / 25 * (0.5 + request.audace)
    value += max(-TASTE_MIN, taste(kinds(item, found["tags"]), request))
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


# The photo filters: an activity without a photo, or whose photo is dead or does not show now, is never proposed.
# Off to try evenings without them: a step without its photo shows the app's picture of its kind (app/src/lib/step-images.ts).
IMAGE_FILTERS = False

# Images checked by this process: an evening never shows a step without its photo (IMAGE_FILTERS).
_IMAGES: dict[str, bool] = {}


def unshown(steps: list[Step]) -> set:
    """The activities of these steps whose image a page cannot show: dead, refused, or not answering now.

    A dead image is first replaced by the official site's when that one shows (`_replace_dead`). Each image is
    checked once per process. None without the photo filters.
    """
    if not IMAGE_FILTERS:
        return set()
    todo = list({images.of(s.candidate.item) for s in steps} - _IMAGES.keys() - {None})
    if todo:
        with httpx.Client(timeout=8, follow_redirects=True, headers=BROWSER_HEADERS) as client, ThreadPoolExecutor(8) as pool:
            verdicts = dict(zip(todo, pool.map(lambda url: images.loads(client, url), todo)))
            _IMAGES.update({url: ok for url, ok in verdicts.items() if ok is not None})
            items = {images.of(s.candidate.item): s.candidate.item for s in steps}
            _replace_dead(client, {url: items[url] for url, ok in verdicts.items() if ok is False}, pool.map)
    return {s.candidate.key for s in steps if _IMAGES.get(images.of(s.candidate.item)) is not True}


def _replace_dead(client: httpx.Client, dead: dict[str, dict[str, Any]], each: Callable = map) -> dict[str, str | None]:
    """These dead images (each of its activity), replaced by the official site's when that one shows: kept in the
    enrichment, and in the activity already loaded. Every one is recorded dead, which leaves an activity still
    without another image out of the next evenings (Base). The new image of each, or None."""
    if not dead:
        return {}
    found = dict(zip(dead, each(lambda url: images.replacement(client, dead[url], url), dead)))
    with open_store(DB) as store:
        store.save_page_checks({url: (images.CHECK, True, None) for url in dead})
        for url, image in found.items():
            _IMAGES[url] = False
            if image:
                item = dead[url]
                item["enrichment"] |= {"image_url": image, "image_origin": "site officiel"}
                store.save_enrichment(item["source_id"], item["external_id"], {"image_url": image, "image_origin": "site officiel"})
                _IMAGES[image] = True
    return found


# Images a page reported it could not show, and the answer given: each checked once per process.
_REPORTED: dict[str, str | None] = {}


def broken_image(base: "Base", key: tuple[str, str], url: str) -> str | None:
    """A page could not show this activity's image, `url`, even on a second try: the image to show instead, or None
    (the page then shows its own picture). The one the activity has now if another replaced it since the page was
    drawn; else `url` checked again, and replaced or recorded dead when it is (`_replace_dead`). An image that loads
    from here, or does not answer now, is left as it is: the page's network, not the image."""
    item = base.by_key.get(key)
    if item is None or not url:
        return None
    if (now := _image_url(item)) and now != url and _IMAGES.get(images.of(item)) is not False:
        return now
    if images.of(item) != url:
        return None
    if url not in _REPORTED:
        with httpx.Client(timeout=8, follow_redirects=True, headers=BROWSER_HEADERS) as client:
            ok = images.loads(client, url)
            if ok is not None:
                _IMAGES[url] = ok
            new = _replace_dead(client, {url: item}).get(url) if ok is False else None
        if ok is None:
            return None
        _REPORTED[url] = _image_url(item) if new else None
    return _REPORTED[url]


def keep_images(route: Route) -> None:
    """The images of a kept evening copied here (images.DIRECTORY), its pages then showing those: they stay until
    the evening, whatever the sites do meanwhile. One that cannot be had stays the site's."""
    urls = {url for s in [*route.steps, *filter(None, [route.night])] if (url := images.of(s.candidate.item))}
    with httpx.Client(timeout=15, follow_redirects=True, headers=BROWSER_HEADERS) as client, ThreadPoolExecutor(8) as pool:
        list(pool.map(lambda url: images.local_copy(url, client), urls))


def pick_shown(routes: list[Route], count: int = 3, taken: list[Route] | None = None) -> list[Route]:
    """`pick`, without the routes of a step whose image does not show (only the routes picked are checked)."""
    left_out: set = set()
    for _ in range(5):
        chosen = pick([r for r in routes if not left_out & {s.candidate.key for s in r.steps}], count, taken)
        found = unshown([s for r in chosen for s in r.steps])
        if not found:
            return chosen
        left_out |= found
    return [r for r in chosen if not left_out & {s.candidate.key for s in r.steps}]


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


VARIETY = 2.0  # score drawn at random for each activity at each composition, up to about one asked vibe
KM_WEIGHT = 1.5  # score lost per km from the step before, on top of the travel time


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
            # Close to the step before first: a redrawn activity should not send the couple across Paris.
            value = _route_score(chain, request) - KM_WEIGHT * km_in
            if value > best_value:
                best, best_value = chain, value
            break  # the earliest session that fits: later ones only add waiting
    return best


def remove_step(route: Route, position: int) -> None:
    """The route without its step `position`: the next step (or the night) is reached from the one before."""
    route.steps.pop(position)
    following = route.steps[position] if position < len(route.steps) else route.night
    if following is None:
        return
    if not position:
        following.travel, following.distance = 0, 0.0  # now the first step
        return
    previous = route.steps[position - 1]
    following.distance = distance_km((previous.candidate.lat, previous.candidate.lon), (following.candidate.lat, following.candidate.lon))
    following.travel = travel_minutes(following.distance)
    if following is route.night:
        following.start = previous.end + timedelta(minutes=following.travel)


# The night ------------------------------------------------------------------
# A couple who sleeps out ends the evening in a hotel, a love room or a secret room near its last step.


def is_hotel(item: dict[str, Any]) -> bool:
    return "hotel" in (item["activity"].get("categories") or [])


def night_price(activity: dict[str, Any]) -> tuple[float, bool]:
    """A room's price for the night, and whether it is a guess (from Time Out's scale, "Prix : €€€", if given)."""
    price, estimated = price_for(activity, "nuit")
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


def night_shown(route: Route, rooms: list[Candidate], request: Request, taken: set) -> Step | None:
    """`night_for`, a room whose image does not show passed over."""
    while (night := night_for(route, rooms, request, taken)) and unshown([night]):
        taken = taken | {night.candidate.key}
    return night


def add_nights(routes: list[Route], rooms: list[Candidate]) -> None:
    """A room for each route whose evening sleeps out, not the same one twice."""
    taken: set = set()
    for route in routes:
        if route.request and route.request.overnight:
            route.night = night_shown(route, rooms, route.request, taken)
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
    if not route.price:
        price = "sans rien dépenser"
    elif request.squad:
        price = f"pour environ {route.price / request.party:.0f} € par personne"
    else:
        price = f"pour environ {route.price:.0f} € à deux"
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


# The secret name of a kept evening, shown to both: "Le Pacte de l'Île Saint-Louis". A word of intrigue drawn
# from the evening's mood, and the quarter it happens in, never a venue.
_SECRET_WORDS = {
    "romance": (["Le Serment", "La Promesse", "Les Confidences", "L'Aveu", "Le Rendez-vous secret", "Le Murmure"],
                {"romantique", "coquin", "detente", "chandelles", "vue", "en_duo", "massage", "spa"}),
    "enigme": (["L'Énigme", "L'Affaire", "Le Code secret", "Les Ombres", "Le Mystère", "Le Dossier"],
               {"defi", "frisson", "insolite", "escape_game", "murder_party", "jeu_de_piste", "souterrain", "dans_le_noir", "cache"}),
    "nuit": (["La Conspiration", "Les Noctambules", "La Nuit blanche", "Le Complot", "La Conjuration"],
             {"fete", "electro", "danse", "nuit"}),
    "scene": (["Le Masque", "Le Sortilège", "L'Illusion", "Le Rideau rouge", "Le Grand Secret"],
              {"rire", "emerveiller", "musique", "spectacle", "theatre", "cabaret", "humour", "magie", "cirque", "concert"}),
    "table": (["Le Festin secret", "L'Alchimie", "Le Banquet", "La Recette interdite"],
              {"savourer", "gastronomique", "degustation", "vin", "mixologie"}),
}
_SECRET_ALWAYS = ["Le Pacte", "Le Secret", "La Clé"]
# A band's evening (Secret Squad) has its own words, by the same moods: "L'Opération de Pigalle", "La Virée du Marais".
_SQUAD_WORDS = {
    "romance": ["La Parenthèse", "Le Grand Jeu", "L'Échappée belle"],
    "enigme": ["L'Opération", "La Mission", "Le Casse", "Le Coup monté"],
    "nuit": ["La Virée", "La Tournée", "La Nuit blanche", "Le Grand Raout"],
    "scene": ["Le Grand Show", "La Grande Tournée", "Le Grand Cirque"],
    "table": ["La Tablée", "Le Banquet", "La Grande Bouffe"],
}
_SQUAD_ALWAYS = ["L'Équipée", "La Bande", "Le Gang"]
# Paris by its quarters, at their heart: the nearest one names the evening.
_QUARTERS = [
    ("l'Île Saint-Louis", 48.8515, 2.3566), ("l'Île de la Cité", 48.8546, 2.3477), ("le Marais", 48.8578, 2.3600),
    ("le Haut-Marais", 48.8635, 2.3620), ("Beaubourg", 48.8606, 2.3522), ("les Halles", 48.8620, 2.3460),
    ("Montorgueil", 48.8655, 2.3470), ("le Palais-Royal", 48.8638, 2.3370), ("les Tuileries", 48.8635, 2.3275),
    ("l'Opéra", 48.8710, 2.3320), ("la Bourse", 48.8690, 2.3410), ("les Grands Boulevards", 48.8715, 2.3460),
    ("Saint-Germain-des-Prés", 48.8540, 2.3330), ("l'Odéon", 48.8510, 2.3390), ("le Quartier latin", 48.8490, 2.3470),
    ("la Contrescarpe", 48.8440, 2.3490), ("le Luxembourg", 48.8462, 2.3372), ("Montparnasse", 48.8430, 2.3240),
    ("Denfert-Rochereau", 48.8340, 2.3320), ("le Champ-de-Mars", 48.8556, 2.2986), ("les Invalides", 48.8566, 2.3126),
    ("le Trocadéro", 48.8620, 2.2880), ("Passy", 48.8550, 2.2780), ("Auteuil", 48.8480, 2.2600),
    ("les Champs-Élysées", 48.8700, 2.3070), ("la Madeleine", 48.8700, 2.3245), ("Monceau", 48.8790, 2.3090),
    ("les Batignolles", 48.8860, 2.3170), ("la Nouvelle Athènes", 48.8790, 2.3360), ("Pigalle", 48.8820, 2.3370),
    ("Montmartre", 48.8867, 2.3431), ("la Goutte-d'Or", 48.8850, 2.3540), ("le Canal Saint-Martin", 48.8710, 2.3650),
    ("Oberkampf", 48.8650, 2.3780), ("la Bastille", 48.8532, 2.3692), ("le Faubourg Saint-Antoine", 48.8510, 2.3780),
    ("Belleville", 48.8720, 2.3770), ("Ménilmontant", 48.8670, 2.3890), ("les Buttes-Chaumont", 48.8800, 2.3830),
    ("la Villette", 48.8900, 2.3900), ("Charonne", 48.8540, 2.3940), ("Bercy", 48.8380, 2.3820),
    ("le Jardin des Plantes", 48.8440, 2.3590), ("la Butte-aux-Cailles", 48.8270, 2.3500), ("Austerlitz", 48.8400, 2.3680),
    ("Vaugirard", 48.8400, 2.3000), ("Grenelle", 48.8480, 2.2920), ("Montsouris", 48.8220, 2.3380),
]
_QUARTER_KM = 1.2  # further from any quarter's heart, the town names the evening, or Paris itself


def _plain(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def _of(place: str) -> str:
    """"de" before a place: du Marais, des Halles, de la Bastille, de l'Opéra, d'Ivry, de Pigalle."""
    if place.startswith("le "):
        return "du " + place[3:]
    if place.startswith("les "):
        return "des " + place[4:]
    if _plain(place[0]) in "aeiouy" and not place.startswith("l'"):
        return "d'" + place
    return "de " + place


def _secret_place(route: Route) -> str:
    """The quarter the evening happens in, unless its name gives a venue away ("Montmartre" for the Musée de Montmartre)."""
    steps = route.steps + ([route.night] if route.night else [])
    said = " ".join(_plain(f"{s.candidate.title} {s.candidate.venue}") for s in steps)
    # The step nearest all the others: a real place of the evening, where a mean of far-apart steps would not be.
    middle = min(route.steps, key=lambda s: sum(distance_km((s.candidate.lat, s.candidate.lon), (o.candidate.lat, o.candidate.lon)) for o in route.steps))
    near = sorted((distance_km((middle.candidate.lat, middle.candidate.lon), (lat, lon)), name) for name, lat, lon in _QUARTERS)
    for km, name in near:
        if km > _QUARTER_KM:
            break
        core = _plain(name.split("'", 1)[1] if name.startswith("l'") else name.split(" ", 1)[1] if name.split(" ", 1)[0] in ("le", "la", "les") else name)
        if core not in said:
            return name
    town = (middle.candidate.item["activity"].get("venue") or {}).get("town")
    return town if town and town != "Paris" and _plain(town) not in said else "la Ville Lumière"


def secret_title(route: Route, squad: bool = False) -> str:
    """The evening's secret name, the same for the same steps: a word of its mood and its quarter, no venue; a band's
    own words for a Secret Squad."""
    flavours = Counter()
    for step in route.steps:
        said = {*step.candidate.tags, *step.candidate.vibes, *(step.candidate.item["activity"].get("categories") or [])}
        for flavour, (_, signs) in _SECRET_WORDS.items():
            flavours[flavour] += len(said & signs)
    mood = max(_SECRET_WORDS, key=lambda f: flavours[f]) if flavours and max(flavours.values()) else None
    if squad:
        words = (_SQUAD_WORDS[mood] if mood else []) + _SQUAD_ALWAYS
    else:
        words = (_SECRET_WORDS[mood][0] if mood else []) + _SECRET_ALWAYS
    seed = int(hashlib.sha1("|".join(":".join(s.candidate.key) for s in route.steps).encode()).hexdigest(), 16)
    return f"{words[seed % len(words)]} {_of(_secret_place(route))}"


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
    who = f"entre amis, à {request.party}," if request.squad else "en couple"
    prompt = (
        f"Voici {len(routes)} parcours de soirée {who} à Paris le {request.day:%d/%m/%Y}, envies : "
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
    """The activity's photo: its copy here if it has one (a kept evening's, `keep_images`), copied first when the
    source forbids showing it elsewhere, else the site's."""
    image = images.of(item)
    if not image:
        return None
    if copy := images.copied(image) or (images.local_copy(image) if images.needs_copy(image) else None):
        return f"/images/{copy.name}"
    return None if images.needs_copy(image) else image


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
        "id": ":".join(map(str, c.key)),  # source_id:external_id, the activity itself (e.g. what is booked)
        "source_id": item["source_id"], "source_name": source_name(item["source_id"]),
        "redo": redo,
    }


def route_json(index: int, route: Route, request: Request | None = None) -> dict[str, Any]:
    """One route (an evening's timeline), its data reshaped for a client to display however it likes; with the
    formula and the party of the evening asked (a couple's when not given), which its clues and words follow."""
    steps = [step_json(step, f"routes/{index}/steps/{position}") for position, step in enumerate(route.steps)]
    request = request or route.request
    squad = bool(request and request.squad)
    return {
        "index": index, "title": route.title, "pitch": route.pitch,
        "secret_title": secret_title(route, squad),  # what all see once it is kept: no venue in it
        "formule": "squad" if squad else "duo", "personnes": request.party if request else 2,
        "day": route.steps[0].start.date().isoformat(),
        "start": route.steps[0].start.isoformat(), "end": route.steps[-1].end.isoformat(),
        "price": route.price, "price_estimated": any(s.candidate.price_estimated for s in route.steps),
        "steps": steps,
        "night": step_json(route.night, None) if route.night else None,
        "redo": f"routes/{index}",
    }


def soiree_json(name: str, state: dict[str, Any]) -> dict[str, Any]:
    """A composed evening (or several), as data: what the client needs to draw it and to ask for a redraw.

    Sent by surprise.quiz; the app (app/src/app/soiree.tsx) lays it out.
    """
    routes, requests = state["routes"], state["requests"]
    request = requests[0]
    return {
        "name": name,
        "naming": bool(state.get("naming")),  # Claude's titles are still coming; poll GET /api/parcours/<name>
        "chosen": bool(state.get("chosen")),  # the couple kept a route: it is the only one left
        "days": [r.day.isoformat() for r in requests],
        "start": request.start.isoformat(), "end": request.end.isoformat(),
        "budget": request.budget, "night_budget": request.room_budget if request.overnight else None,
        "vibes": request.vibes, "trame": request.trame,
        # Secret Date ("duo") or Secret Squad ("squad"), and how many go out: every price counts them all.
        "formule": request.formule, "personnes": request.party,
        "routes": [route_json(index, route, request) for index, route in enumerate(routes)],
    }


def _weekday(day: date) -> str:
    return ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"][day.weekday()]


# Command line ---------------------------------------------------------------


def shown(item: dict[str, Any]) -> bool:
    """An evening's step is shown with a photo and a text: an activity lacking either is never proposed (a photo only
    with IMAGE_FILTERS)."""
    return (not IMAGE_FILTERS or bool(images.of(item))) and bool(item["enrichment"].get("description") or (item.get("lead_text") or "").strip())


@dataclass
class Base:
    """The activities that can be steps, with their originality: loaded once for several evenings."""

    items: list[dict[str, Any]]
    originality: dict[tuple[str, str], int]

    @classmethod
    def load(cls, store: LocalStore) -> "Base":
        # Nor an image recorded dead (python -m surprise.images), with the photo filters.
        dead = {url for url, (engine, closed, _) in store.page_checks().items() if engine == images.CHECK and closed} if IMAGE_FILTERS else set()
        items = [
            item for item in store.list_for_moderation()
            if item["status"] not in ("rejected", "filtered") and shown(item) and images.of(item) not in dead
        ]
        scorer = Scorer(items)
        return cls(items, {(i["source_id"], i["external_id"]): scorer.score(i).score for i in items})

    @cached_property
    def by_key(self) -> dict[tuple[str, str], dict[str, Any]]:
        return {(i["source_id"], i["external_id"]): i for i in self.items}


def plan(store: LocalStore, request: Request, checks: int = 60, count: int = 3, base: Base | None = None) -> list[Route]:
    return pick(evening_routes(candidates_for(store, base or Base.load(store), request, checks), request), count)


def evening_routes(candidates: list[Candidate], request: Request) -> list[Route]:
    """Every route found for the evening from its candidates, with a new draw of luck, best first."""
    routes = compose(lucky(candidates), request)
    for route in routes:
        route.request = request
    return routes


def lucky(candidates: list[Candidate]) -> list[Candidate]:
    """The candidates with a draw of luck (VARIETY) on their score, so that two compositions of the same evening,
    or two redraws from the candidates kept, differ."""
    return [replace(c, score=c.score + random.uniform(0, VARIETY)) for c in candidates]


def candidates_for(store: LocalStore, base: Base, request: Request, checks: int = 60) -> list[Candidate]:
    """The activities that can be a step that evening, scored without luck (`lucky` draws it); the activities
    checked for it get a draw of luck (VARIETY), so that two compositions of the same evening check others."""
    items = base.items
    checked = check_engines(store, items, request, checks, _prescore(items, request, base)) if checks else store.cached_availability(
        request.day.isoformat(), request.party, CACHE_HOURS
    )
    candidates = _scored(items, request, checked, base)
    kinds = Counter(c.kind for c in candidates)
    print(
        f"{len(candidates)} étapes possibles ce soir-là : {kinds['seance']} séances, {kinds['verifie']} créneaux vérifiés, "
        f"{kinds['gratuit']} gratuites, {kinds['sans_resa']} sans réservation"
    )
    return candidates


def more_candidates(
    store: LocalStore, base: Base, request: Request, known: set, checks: int, role_: str | None = None,
) -> list[Candidate]:
    """Steps of the evening besides the `known` activities: the booking engines asked for `checks` activities not yet
    checked that evening (`role_`: only those that would play this part), the answers other compositions got since
    read too. Those with dated sessions or walked into are all among the candidates already."""
    items = [
        item for item in base.items
        if needs_check(item) and (item["source_id"], item["external_id"]) not in known
        and (role_ is None or role(item["activity"], describe(item["activity"])["tags"], request.no_dinner) == role_)
    ]
    checked = check_engines(store, items, request, checks, _prescore(items, request, base))
    return _scored([item for item in items if (item["source_id"], item["external_id"]) in checked], request, checked, base)


def _prescore(items: list[dict[str, Any]], request: Request, base: Base) -> dict:
    """The activities' rank for the live checks, with a draw of luck (VARIETY) so that two compositions check others."""
    return {
        key: quick_score(i, request, base.originality[key]) + random.uniform(0, VARIETY)
        for i in items if (key := (i["source_id"], i["external_id"]))
    }


def _scored(items: list[dict[str, Any]], request: Request, checked: dict, base: Base) -> list[Candidate]:
    """These activities as steps of the evening, scored without luck: those that cannot be one, or done already, left out."""
    candidates = []
    for item in items:
        key = (item["source_id"], item["external_id"])
        if key in request.done:
            continue
        candidate = build_candidate(item, request, checked.get(key), base.originality[key])
        if candidate:
            candidate.score = score(candidate, request)
            if candidate.score > -math.inf:
                candidates.append(candidate)
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
    parser.add_argument("--squad", type=int, metavar="N", help="Secret Squad : une soirée entre amis à N (--budget pour toute la bande)")
    parser.add_argument("--db", help="base SQLite ou URL postgresql:// (défaut : SUPABASE_DB_URL, sinon data/surprise.db)")
    parser.add_argument("--no-claude", action="store_true", help="titres et pitchs par règles, sans Claude")
    parser.add_argument("--no-open", action="store_true", help="ne pas ouvrir la soirée dans l'app")
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
            day, args.budget, begin, finish, vibes, walk_in=not args.strict, trame=trame, max_travel=args.trajet_max,
            overnight=args.decoucher and not args.squad, night_budget=args.budget_nuit,
            party=args.squad or 2, formule="squad" if args.squad else "duo",
        ))

    with open_store(args.db) as store:
        routes, name = generate(store, requests, args.parcours, args.checks, claude=not args.no_claude)
    who = f"à {args.squad}" if args.squad else "à deux"
    for index, route in enumerate(routes, 1):
        print(f"\n{index}. {_weekday(route.request.day)} {route.request.day:%d/%m} · {route.title} — {route.price:.0f} € {who}")
        for step in route.steps:
            print(f"   {step.start:%H:%M}-{step.end:%H:%M}  {step.candidate.title[:70]}  [{step.basis}]")
        if night := route.night:
            price = f"{'≈ ' if night.candidate.price_estimated else 'dès '}{night.candidate.price:.0f} €"
            print(f"   {night.start:%H:%M}-{night.end:%H:%M}  nuit : {night.candidate.title[:60]}  [{price}, {night.travel} min]")
    # Shown by the app, as served by surprise.quiz (which must be running).
    url = f"http://127.0.0.1:8001/soiree?soiree={name}"
    print(f"\nDans l'app : {url}")
    if not args.no_open:
        webbrowser.open(url)


def generate(
    store: LocalStore, requests: list[Request], count: int, checks: int = 60, claude: bool = True, name: str | None = None,
    base: Base | None = None, name_later: bool = False,
) -> tuple[list[Route], str]:
    """The best routes over the evenings asked, named, and the name they are saved under (see `soiree_json`).

    `base`: the activities already loaded (a server keeps them). `name_later`: routes are saved at
    once, named by rules, and Claude's titles replace them when they come (`soiree_json`'s `naming`).
    The candidates of each evening are saved with it: a redraw starts from them until a route is chosen.
    """
    base = base or Base.load(store)
    routes: list[Route] = []
    pools: list[list[Candidate]] = []
    for request in requests:
        if len(requests) > 1:
            print(f"\n— {_weekday(request.day)} {request.day:%d/%m}")
        pools.append(candidates_for(store, base, request, checks))
        routes += evening_routes(pools[-1], request)
    # The best routes of all evenings together, without a step in common.
    routes = pick_shown(sorted(routes, key=lambda route: -route.score), count)
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
    # Unique: the page's name is the evening's id in the store.
    name = name or f"{days[0].isoformat()}{'' if len(days) == 1 else '_' + days[-1].isoformat()}-{secrets.token_urlsafe(6)}"
    state = {"routes": routes, "requests": requests, "seen": {s.candidate.key for r in routes for s in r.steps}, "naming": int(later)}
    with _SAVING:
        save(name, state, store, candidates=pools)
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
# The page's routes are kept in the store (soirees, soiree_routes, soiree_steps), so that one route, or one step
# of a route, can be drawn again from the page. Activities already shown are not proposed again
# while others fit. Until the couple chooses a route, the evening's candidates are kept too (soiree_candidates):
# a redraw starts from them. Once a route is chosen, the evening is that route alone.


# A page is loaded, changed and saved again by the composition, a redraw and Claude's titles: one at a time.
_SAVING = threading.RLock()


_TYPES = {cls.__name__: cls for cls in (Request, Candidate, Step)}


def _encode(value: Any) -> Any:
    """JSON for the store, the types JSON lacks tagged: dataclasses, dates, sets, non-string keys, infinities."""
    if is_dataclass(value):
        return {"_type": type(value).__name__, **{f.name: _encode(getattr(value, f.name)) for f in fields(value)}}
    if isinstance(value, datetime):
        return {"_datetime": value.isoformat()}
    if isinstance(value, date):
        return {"_date": value.isoformat()}
    if isinstance(value, (set, frozenset)):
        return {"_set": [_encode(v) for v in sorted(value, key=repr)]}
    if isinstance(value, tuple):
        return {"_tuple": [_encode(v) for v in value]}
    if isinstance(value, dict):
        if all(isinstance(k, str) for k in value):
            return {k: _encode(v) for k, v in value.items()}
        return {"_pairs": [[_encode(k), _encode(v)] for k, v in value.items()]}
    if isinstance(value, list):
        return [_encode(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return {"_float": repr(value)}
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode(v) for v in value]
    if not isinstance(value, dict):
        return value
    if "_datetime" in value:
        moment = datetime.fromisoformat(value["_datetime"])
        return moment.astimezone(PARIS) if moment.tzinfo else moment
    if "_date" in value:
        return date.fromisoformat(value["_date"])
    if "_set" in value:
        return {_decode(v) for v in value["_set"]}
    if "_tuple" in value:
        return tuple(_decode(v) for v in value["_tuple"])
    if "_pairs" in value:
        return {_decode(k): _decode(v) for k, v in value["_pairs"]}
    if "_float" in value:
        return float(value["_float"])
    if "_type" in value:
        return _TYPES[value["_type"]](**{k: _decode(v) for k, v in value.items() if k != "_type"})
    return {k: _decode(v) for k, v in value.items()}


def _json(value: Any) -> str:
    # Postgres jsonb refuses the NUL character, which a few scraped pages carry.
    return json.dumps(_encode(value), ensure_ascii=False).replace("\\u0000", "")


def _own(store: LocalStore | None) -> contextlib.AbstractContextManager[LocalStore]:
    """The store given, left open; else one opened on DB for the while (one connection: under a second through the pooler)."""
    return contextlib.nullcontext(store) if store else open_store(DB)


def _candidates_json(candidates: list[Candidate]) -> str:
    """The candidates for the store, each activity by its key: the server has the activities loaded (Base)."""
    return _json([{"key": c.key, **{f.name: getattr(c, f.name) for f in fields(c) if f.name != "item"}} for c in candidates])


def _candidates_from(text: str, base: Base) -> list[Candidate]:
    """The candidates kept, on the activities loaded; one that left the base since (rejected in moderation) is not."""
    found = []
    for data in _decode(json.loads(text)):
        if (item := base.by_key.get(data.pop("key"))) is not None:
            found.append(Candidate(item=item, **data))
    return found


def save(name: str, state: dict[str, Any], store: LocalStore | None = None, candidates: list[list[Candidate]] | None = None) -> None:
    """A composed evening in the store (soirees, soiree_routes, soiree_steps), under this name, so a route or a
    step of it can be drawn again (see `regenerate`). The activities already shown are its steps, replaced ones too.

    `candidates`: those of each evening asked, kept for the redraws until a route is chosen (`choose`).
    """
    requests = state["requests"]
    routes = [
        (index, requests.index(route.request) if route.request in requests else None, route.title, route.pitch, route.score)
        for index, route in enumerate(state["routes"])
    ]
    steps = [
        (index, position, *step.candidate.key, step.start.isoformat(), step.end.isoformat(), step is route.night, _json(step))
        for index, route in enumerate(state["routes"])
        for position, step in enumerate([*route.steps, *filter(None, [route.night])])
    ]
    with _own(store) as store:
        store.save_soiree(name, _json(requests), int(state.get("naming") or 0), routes, steps)
        if candidates is not None:
            store.save_candidates(name, {at: _candidates_json(found) for at, found in enumerate(candidates)}, CACHE_HOURS)


def load(name: str, store: LocalStore | None = None) -> dict[str, Any] | None:
    with _own(store) as store:
        data = store.soiree(name)
    if data is None:
        return None
    requests = _decode(json.loads(data["requests"]))
    steps: dict[int, list[Step]] = {}
    nights: dict[int, Step] = {}
    for route, night, step in data["steps"]:
        if night:
            nights[route] = _decode(json.loads(step))
        else:
            steps.setdefault(route, []).append(_decode(json.loads(step)))
    routes = [
        Route(steps.get(index, []), score, title, pitch, None if request is None else requests[request], nights.get(index))
        for index, request, title, pitch, score in data["routes"]
    ]
    seen = {(source_id, external_id) for source_id, external_id in data["seen"]}
    return {
        "routes": routes, "requests": requests, "seen": seen, "naming": data["naming"], "chosen": data["chosen"],
        "sizes": data.get("sizes") or {},
    }


def regenerate(
    store: LocalStore | None, base: Base, name: str, index: int, position: int | None = None, checks: int = 10, claude: bool = True,
) -> str | None:
    """Draws route `index` again, or only its step `position`, and rewrites the page; the error, if any.

    While the couple chooses, from the candidates kept at the composition (CACHE_HOURS at most, as the engines'
    answers): no activity read nor checked again. Once a route is chosen, from candidates found anew, checked live.
    """
    with _SAVING, _own(store) as store:
        return _regenerate(store, base, name, index, position, checks, claude)


def choose(name: str, index: int, store: LocalStore | None = None) -> str | None:
    """The couple keeps route `index`: the evening is that route alone from now on, its name enough to find it; the
    other routes and the candidates go, its images are copied here (`keep_images`). The error, if any."""
    with _SAVING, _own(store) as store:
        if not store.keep_route(name, index):
            return "parcours introuvable : relancez la composition"
        state = load(name, store)
    keep_images(state["routes"][0])
    return None


def _candidates(store: LocalStore, base: Base, name: str, state: dict[str, Any], request: Request, checks: int) -> list[Candidate]:
    """The candidates of the evening asked: kept since its composition, or found anew and kept until a route is chosen."""
    at = _asked(state, request)
    if not state["chosen"] and (kept := store.soiree_candidates(name, at, CACHE_HOURS)) is not None:
        return _candidates_from(kept, base)
    found = candidates_for(store, base, request, checks)
    if not state["chosen"]:
        store.save_candidates(name, {at: _candidates_json(found)}, CACHE_HOURS)
    return found


def _asked(state: dict[str, Any], request: Request) -> int:
    return state["requests"].index(request) if request in state["requests"] else 0


def _search(
    store: LocalStore, base: Base, name: str, state: dict[str, Any], request: Request, pool: list[Candidate], checks: int,
    role_: str | None = None,
) -> list[Candidate]:
    """`more_candidates` for a redraw, added to the evening's `pool` and kept with it until a route is chosen."""
    more = more_candidates(store, base, request, {c.key for c in pool}, checks, role_)
    pool += more
    if more and not state["chosen"]:
        store.save_candidates(name, {_asked(state, request): _candidates_json(pool)}, CACHE_HOURS)
    return more


def _replace_shown(route: Route, position: int, candidates: list[Candidate], request: Request, excluded: set) -> list[Step] | None:
    """`replace_step`, past the activities whose image a page cannot show."""
    unshown_keys: set = set()
    for _ in range(5):
        steps = replace_step(route, position, candidates, request, excluded | unshown_keys)
        if not steps or not (found := unshown([steps[position]])):
            return steps
        unshown_keys |= found
    return None


def remove(name: str, index: int, position: int) -> str | None:
    """Takes step `position` out of route `index`, the couple's choice; the error, if any."""
    with _SAVING:
        state = load(name)
        if state is None:
            return "parcours introuvable : relancez la composition"
        routes = state["routes"]
        if not 0 <= index < len(routes) or not 0 <= position < len(routes[index].steps):
            return "étape inconnue"
        if len(routes[index].steps) < 2:
            return "une soirée garde au moins une étape"
        remove_step(routes[index], position)
        save(name, state)
    return None


def _regenerate(store: LocalStore, base: Base, name: str, index: int, position: int | None, checks: int, claude: bool) -> str | None:
    state = load(name, store)
    if state is None:
        return "parcours introuvable : relancez la composition"
    routes = state["routes"]
    if not 0 <= index < len(routes) or (position is not None and not 0 <= position < len(routes[index].steps)):
        return "étape inconnue"
    route = routes[index]
    request = route.request or state["requests"][0]
    pool = _candidates(store, base, name, state, request, checks)
    candidates = lucky(pool)
    on_page = {s.candidate.key for r in routes for s in r.steps}
    # Once every activity kept that would do was proposed, others are looked for (`_search`) rather than going round
    # the ones shown already: a step redrawn never brings back an activity the page had, a route only when none all
    # new is found.
    if position is None:
        # None of the route's activities again, under the same listing or another one.
        keys, titles = {s.candidate.key for s in route.steps}, {_same(s.candidate.title) for s in route.steps}
        venues = {s.candidate.venue.lower() for s in route.steps} - {""}
        # As many steps as the route had when composed, the ones the couple took out included, if such routes exist.
        size = max(len(route.steps), state["sizes"].get(index, 0))
        others = [r for r in routes if r is not route]

        def drawn(candidates: list[Candidate]) -> list[Route]:
            found = compose([c for c in candidates if c.key not in keys and _same(c.title) not in titles and c.venue.lower() not in venues], request)
            return [r for r in found if len(r.steps) >= size] or found

        def shown_before(drawn_route: Route) -> int:
            return len({s.candidate.key for s in drawn_route.steps} & state["seen"])

        found = drawn(candidates)
        chosen = pick_shown([r for r in found if not shown_before(r)], 1, others)
        for _ in range(SEARCH_ROUNDS):
            if chosen:
                break
            if more := _search(store, base, name, state, request, pool, checks):
                candidates += lucky(more)
                found = drawn(candidates)
                chosen = pick_shown([r for r in found if not shown_before(r)], 1, others)
        # No route all new: the one with the fewest activities shown already, rather than a route shown before.
        for count in sorted({shown_before(r) for r in found}):
            if chosen:
                break
            chosen = pick_shown([r for r in found if shown_before(r) == count], 1, others)
        if not chosen:
            return "aucun autre parcours complet ce soir-là"
        new = chosen[0]
    else:
        excluded = state["seen"] | on_page
        # Nor one of them under another listing (a show sold on two platforms).
        titles = {_same(c.title) for c in pool if c.key in excluded} | {_same(s.candidate.title) for r in routes for s in r.steps}

        def unseen(found: list[Candidate]) -> list[Candidate]:
            return [c for c in found if _same(c.title) not in titles]

        steps = _replace_shown(route, position, unseen(candidates), request, excluded)
        for _ in range(SEARCH_ROUNDS):
            if steps:
                break
            # Only activities that would play the same part are checked: a dinner for a dinner.
            if more := _search(store, base, name, state, request, pool, checks, route.steps[position].candidate.role):
                steps = _replace_shown(route, position, unseen(lucky(more)), request, excluded)
        if not steps:
            return "plus d'autre activité qui s'enchaîne à cette étape ce soir-là"
        new = Route(steps, _route_score(steps, request))
    new.request = request
    if request.overnight:
        # Its room again if it still fits, else another one than the other routes'.
        others = {r.night.candidate.key for r in routes if r is not route and getattr(r, "night", None)}
        new.night = night_shown(new, hotels(base), request, others)
    name_by_rules(new, request)
    later = claude and bool(os.environ.get("ANTHROPIC_API_KEY"))
    routes[index] = new
    state["seen"] |= {s.candidate.key for s in new.steps}
    state["naming"] = int(state.get("naming") or 0) + later
    save(name, state, store)
    if later:
        threading.Thread(target=_name_later, args=(name, [new], request), daemon=True).start()
    return None

if __name__ == "__main__":
    main()
