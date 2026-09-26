"""Client questionnaire: a short, playful quiz that draws the couple's profile, then their evenings.

The quiz asks what lasts: each answer weighs on the vibes (surprise.tags.VIBES)
and sets the couple's appetite for the unusual (audace), what they never want,
the music they like, the budget, their usual end of evening and the day of their
first outing; no precise hour. The profile keeps the weighted vibes, the main
ones, a persona to tell them who they are ("Les Explorateurs"), and is stored
with the answers (table profiles).

Each evening is asked apart, on its own page (/soiree): up to three wishes
(ENVIES: party tonight, cocooning another night) and maybe an occasion
(OCCASIONS) set that evening's vibes and hours, while refusals, budget, audace
and tastes come from the profile, when there is one. From both,
surprise.parcours composes the evening.

    uv run python -m surprise.quiz            # http://127.0.0.1:8001, the evening at /soiree

Served on 127.0.0.1 with the standard library, like the moderation page.
"""

import argparse
import json
import re
import secrets
import sys
import threading
import time as clock
import webbrowser
from datetime import date, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from surprise import images, parcours
from surprise.local_store import DEFAULT_PATH, LocalStore
from surprise.tags import VIBES

RESOURCES = files("surprise")
# Pages and the style and script they share.
STATIC = {
    "/": ("quiz.html", "text/html; charset=utf-8"),
    "/soiree": ("soiree.html", "text/html; charset=utf-8"),
    "/client.css": ("client.css", "text/css; charset=utf-8"),
    "/client.js": ("client.js", "text/javascript; charset=utf-8"),
}

# The profile's questions: what lasts from one evening to the next, no precise hour.
# id, question, hint, kind ("single", "multi", "scale", "date", "text"), options.
# An option: value, label, emoji, and what it does: vibe weights, audace, avoid, prefer, end, budget, dinner.
QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "couple", "kind": "single",
        "question": "Votre histoire en est où ?", "hint": "Pour viser juste dès la première soirée.",
        "options": [
            {"value": "debut", "label": "On se découvre", "emoji": "🌱", "vibes": {"rire": 1, "defi": 1}, "avoid": ["dans_le_noir"]},
            {"value": "complices", "label": "Complices depuis un moment", "emoji": "🤝", "vibes": {"rire": 1, "insolite": 1}},
            {"value": "installes", "label": "Installés, envie de pimenter", "emoji": "🌶️", "vibes": {"insolite": 1, "romantique": 1}},
            {"value": "longue", "label": "Une longue histoire à célébrer", "emoji": "💞", "vibes": {"romantique": 2, "savourer": 1}},
        ],
    },
    {
        "id": "debut_soiree", "kind": "single",
        "question": "Votre soirée idéale commence par…", "hint": None,
        "options": [
            {"value": "terrasse", "label": "Un verre au soleil couchant", "emoji": "🌇", "vibes": {"savourer": 1, "flaner": 1, "romantique": 1}},
            {"value": "culture", "label": "Un lieu chargé d'histoire", "emoji": "🏛️", "vibes": {"cultiver": 2}},
            {"value": "defi", "label": "Un défi à deux", "emoji": "🧩", "vibes": {"defi": 2}},
            {"value": "cocon", "label": "Un moment rien qu'à nous", "emoji": "🕯️", "vibes": {"romantique": 2, "detente": 1}},
            {"value": "creer", "label": "Mettre les mains à la pâte", "emoji": "🎨", "vibes": {"creer": 2}},
        ],
    },
    {
        "id": "energie", "kind": "scale",
        "question": "Plutôt plaid ou dancefloor ?", "hint": "De 1, on se pose, à 5, on ne tient pas en place.",
        "options": [
            {"value": 1, "label": "Plaid", "emoji": "🛋️", "vibes": {"detente": 2}},
            {"value": 2, "label": "", "emoji": "🍵", "vibes": {"detente": 1, "cultiver": 1}},
            {"value": 3, "label": "", "emoji": "🚶", "vibes": {"flaner": 1}},
            {"value": 4, "label": "", "emoji": "🕺", "vibes": {"bouger": 1, "musique": 1}},
            {"value": 5, "label": "Dancefloor", "emoji": "🪩", "vibes": {"fete": 2, "bouger": 1}},
        ],
    },
    {
        "id": "reussie", "kind": "multi", "max": 2,
        "question": "Une soirée réussie, c'est quand…", "hint": "Deux réponses au plus.",
        "options": [
            {"value": "rire", "label": "On a ri aux larmes", "emoji": "😂", "vibes": {"rire": 2}},
            {"value": "yeux", "label": "On en a pris plein les yeux", "emoji": "🤩", "vibes": {"emerveiller": 2}},
            {"value": "appris", "label": "On a appris un truc", "emoji": "🧠", "vibes": {"cultiver": 2}},
            {"value": "mains", "label": "On repart avec un objet fait main", "emoji": "🏺", "vibes": {"creer": 2}},
            {"value": "musique", "label": "On a vibré sur de la musique", "emoji": "🎷", "vibes": {"musique": 2}},
            {"value": "frissons", "label": "On a eu des frissons", "emoji": "👻", "vibes": {"frisson": 2}},
            {"value": "gagne", "label": "On a gagné (ensemble)", "emoji": "🏆", "vibes": {"defi": 2}},
        ],
    },
    {
        "id": "audace", "kind": "single",
        "question": "Jusqu'où osez-vous ?", "hint": "Pour savoir à quel point vous surprendre.",
        "options": [
            {"value": "classique", "label": "Du classique qui marche", "emoji": "🎩", "audace": 0.1},
            {"value": "pointe", "label": "Une pointe d'originalité", "emoji": "🌶️", "audace": 0.4, "vibes": {"insolite": 1}},
            {"value": "surprenez", "label": "Surprenez-nous", "emoji": "🎁", "audace": 0.7, "vibes": {"insolite": 2}},
            {"value": "fou", "label": "Plus c'est fou, mieux c'est", "emoji": "🚀", "audace": 1.0, "vibes": {"insolite": 3}},
        ],
    },
    {
        "id": "assiette", "kind": "single",
        "question": "Et côté assiette ?", "hint": None,
        "options": [
            {"value": "table", "label": "Une vraie belle table", "emoji": "🍽️", "vibes": {"savourer": 2}, "dinner": True},
            {"value": "partage", "label": "Des assiettes à partager", "emoji": "🥂", "vibes": {"savourer": 1}},
            {"value": "pouce", "label": "Sur le pouce, on a mieux à faire", "emoji": "🌮", "vibes": {}},
            {"value": "secondaire", "label": "Manger, pas notre priorité", "emoji": "🤷", "vibes": {}},
        ],
    },
    {
        "id": "musique", "kind": "multi", "max": 3,
        "question": "La bande-son de votre couple ?", "hint": "Trois au plus, ou aucune.",
        "options": [
            {"value": "jazz", "label": "Jazz & soul", "emoji": "🎺", "prefer": ["jazz"], "vibes": {"musique": 1}},
            {"value": "classique", "label": "Classique", "emoji": "🎻", "prefer": ["classique", "chandelles"], "vibes": {"musique": 1, "romantique": 1}},
            {"value": "electro", "label": "Électro & house", "emoji": "🎧", "prefer": ["electro"], "vibes": {"fete": 1}},
            {"value": "rock", "label": "Rock & indé", "emoji": "🎸", "prefer": ["concert_live"], "vibes": {"musique": 1}},
            {"value": "chanson", "label": "Chanson & variété", "emoji": "🎤", "prefer": ["karaoke", "cabaret"], "vibes": {"musique": 1}},
            {"value": "latino", "label": "Latino & afro", "emoji": "💃", "prefer": ["danse"], "vibes": {"fete": 1, "bouger": 1}},
        ],
    },
    {
        "id": "fin", "kind": "single",
        "question": "D'habitude, vos soirées finissent…", "hint": "Un soir de fête pourra aller plus loin.",
        "options": [
            {"value": "tot", "label": "Avant minuit", "emoji": "🌙", "end": "23:30"},
            {"value": "verre", "label": "Sur un dernier verre", "emoji": "🍸", "end": "00:30", "vibes": {"savourer": 1}},
            {"value": "danser", "label": "Au bout de la nuit", "emoji": "🌃", "end": "03:30", "vibes": {"fete": 3}},
        ],
    },
    {
        "id": "eviter", "kind": "multi",
        "question": "Ce que vous ne voulez jamais", "hint": "Aucune soirée ne vous le proposera. Autant de réponses que vous voulez.",
        "options": [
            {"value": "maillot", "label": "Être en maillot de bain", "emoji": "🩱", "avoid": ["spa", "flottaison", "baignade"]},
            {"value": "noir", "label": "Le noir complet", "emoji": "🌑", "avoid": ["dans_le_noir"]},
            {"value": "peur", "label": "Les frissons, la peur", "emoji": "😱", "avoid": ["frisson", "souterrain", "murder_party"]},
            {"value": "enfermes", "label": "Être enfermés, sous terre", "emoji": "🔒", "avoid": ["escape_game", "souterrain", "dans_le_noir", "flottaison"]},
            {"value": "hauteur", "label": "Le vide, la hauteur", "emoji": "🧗", "avoid": ["hauteur"]},
            {"value": "effort", "label": "Transpirer", "emoji": "🥵", "avoid": ["sport", "jeu_actif", "defouloir", "sensations"]},
            {"value": "alcool", "label": "L'alcool", "emoji": "🚱", "avoid": ["mixologie", "vin", "cocktails", "vins nature"]},
            {"value": "scene", "label": "Être mis en scène", "emoji": "🎭", "avoid": ["interactif", "karaoke"]},
            {"value": "danser", "label": "Danser", "emoji": "🙅", "avoid": ["danse"]},
            {"value": "foule", "label": "La foule, les boîtes bondées", "emoji": "👥", "avoid": ["grande_salle", "nuit"]},
            {"value": "assis", "label": "Rester assis deux heures", "emoji": "🪑", "avoid": ["theatre", "cinema", "lecture", "comedie_musicale"]},
            {"value": "eau", "label": "Les bateaux", "emoji": "⛵", "avoid": ["sur_l_eau"]},
            {"value": "animaux", "label": "Les animaux", "emoji": "🐾", "avoid": ["animaux"]},
            {"value": "ecrans", "label": "Les écrans, le virtuel", "emoji": "🥽", "avoid": ["jeu_video"]},
        ],
    },
    {
        "id": "budget", "kind": "single",
        "question": "Votre budget pour deux ?", "hint": "Hors transport, tout compris.",
        "options": [
            {"value": "doux", "label": "Moins de 60 €", "emoji": "🪙", "budget": 60},
            {"value": "moyen", "label": "60 à 120 €", "emoji": "💶", "budget": 120},
            {"value": "genereux", "label": "120 à 200 €", "emoji": "💳", "budget": 200},
            {"value": "folie", "label": "On ne compte pas", "emoji": "💎", "budget": 350},
        ],
    },
    {"id": "premiere", "kind": "date", "question": "Votre première sortie ?", "hint": "Le jour qui vous tente ; l'envie de la soirée, on vous la demandera juste avant."},
    {"id": "prenoms", "kind": "text", "question": "Et vous êtes ?", "hint": "Vos prénoms, pour personnaliser vos soirées (facultatif)."},
]

# The wishes of one evening, MAX_ENVIES at most, asked each time: they set that evening's vibes and hours,
# the profile the rest. value, label, emoji, vibes (none: the profile's), and optionally start, end, dinner,
# audace, avoid (dropped when another wish of the evening asks for it: party and cocooning go together).
MAX_ENVIES = 3
ENVIES: list[dict[str, Any]] = [
    {"value": "nous", "label": "Fidèles à nous-mêmes", "emoji": "💫", "vibes": []},
    {"value": "fete", "label": "Faire la fête", "emoji": "🪩", "vibes": ["fete", "musique"], "start": "20:00", "end": "03:30"},
    {"value": "cocooning", "label": "Cocooning", "emoji": "🧸", "vibes": ["detente", "romantique", "savourer"], "end": "23:30",
     "avoid": ["nuit", "electro", "danse", "sport", "jeu_actif", "defouloir", "grande_salle", "frisson"]},
    {"value": "romantique", "label": "Romantique", "emoji": "🕯️", "vibes": ["romantique", "savourer", "emerveiller"], "dinner": True},
    {"value": "rire", "label": "Rire aux éclats", "emoji": "😂", "vibes": ["rire", "defi"]},
    {"value": "jouer", "label": "Jouer, relever un défi", "emoji": "🧩", "vibes": ["defi", "bouger"]},
    {"value": "curieux", "label": "Apprendre, s'émerveiller", "emoji": "🏛️", "vibes": ["cultiver", "emerveiller"]},
    {"value": "creer", "label": "Créer de nos mains", "emoji": "🎨", "vibes": ["creer", "savourer"]},
    {"value": "gourmand", "label": "Se régaler", "emoji": "🍽️", "vibes": ["savourer"], "dinner": True},
    {"value": "musique", "label": "Vibrer en musique", "emoji": "🎷", "vibes": ["musique", "emerveiller"]},
    {"value": "air", "label": "Prendre l'air", "emoji": "🌿", "vibes": ["flaner", "savourer"], "start": "18:30"},
    {"value": "frissons", "label": "Frissonner", "emoji": "👻", "vibes": ["frisson", "insolite"]},
    {"value": "surprise", "label": "Surprenez-nous", "emoji": "🎁", "vibes": [], "audace": 0.3},
]

# What the evening celebrates, if anything: added to its wishes.
OCCASIONS: list[dict[str, Any]] = [
    {"value": "anniversaire", "label": "Un anniversaire", "emoji": "🎂", "vibes": ["romantique"], "dinner": True},
    {"value": "retrouvailles", "label": "Des retrouvailles", "emoji": "🫶", "vibes": ["romantique"]},
    {"value": "grande", "label": "Une grande occasion", "emoji": "💍", "vibes": ["romantique", "emerveiller"], "dinner": True},
    {"value": "rien", "label": "Rien, juste l'envie", "emoji": "✨", "vibes": []},
]

# Persona: the vibes that make it, its name and how it describes the couple.
PERSONAS = [
    ({"insolite", "frisson"}, "Les Explorateurs", "Les adresses secrètes et les expériences jamais vues, c'est votre terrain de jeu."),
    ({"romantique", "detente"}, "Les Romantiques", "Des moments à deux, des lumières douces, le temps qui s'arrête."),
    ({"savourer"}, "Les Épicuriens", "Pour vous, une soirée se juge d'abord à ce qu'on a goûté."),
    ({"fete", "musique"}, "Les Noctambules", "La nuit est jeune, et vous aussi : musique, danse, et on verra bien."),
    ({"cultiver", "emerveiller"}, "Les Curieux", "Vous sortez pour apprendre, voir, et en prendre plein les yeux."),
    ({"defi", "rire", "bouger"}, "Les Complices", "Jouer, rire, gagner ensemble : votre couple est une équipe."),
    ({"creer"}, "Les Créatifs", "Vous aimez repartir avec quelque chose fait de vos mains."),
    ({"flaner"}, "Les Flâneurs", "Paris à pied, au fil de l'eau, sans se presser."),
]
DEFAULT_START = "19:00"  # an evening's first step, unless its wish says otherwise
DEFAULT_END = "00:30"


def profile_from(answers: dict[str, Any]) -> dict[str, Any]:
    """The couple's profile from their answers: weighted vibes, main vibes, persona, audace, refusals, budget, usual end."""
    weights = {key: 0.0 for key in VIBES}
    audace, avoid, prefer, dinner = 0.5, set(), set(), False
    budget, end = 120, DEFAULT_END
    for question in QUESTIONS:
        chosen = answers.get(question["id"])
        values = chosen if isinstance(chosen, list) else [chosen]
        for option in question.get("options") or []:
            if option["value"] not in values:
                continue
            for vibe, weight in (option.get("vibes") or {}).items():
                weights[vibe] += weight
            audace = option.get("audace", audace)
            avoid |= set(option.get("avoid") or [])
            prefer |= set(option.get("prefer") or [])
            dinner = dinner or bool(option.get("dinner"))
            budget = option.get("budget", budget)
            end = option.get("end", end)
    ranked = sorted((v for v in weights if weights[v] > 0), key=lambda v: -weights[v])
    top = weights[ranked[0]] if ranked else 0
    # The main vibes: those weighing at least a third of the strongest, four at most.
    main = [v for v in ranked if weights[v] >= top / 3][:4] or ["romantique"]
    persona = max(PERSONAS, key=lambda p: sum(weights[v] for v in p[0]) / len(p[0]) ** 0.5)
    return {
        "vibes": main,
        "weights": {v: weights[v] for v in ranked},
        "persona": {"name": persona[1], "text": persona[2]},
        "audace": audace,
        "avoid": sorted(avoid),
        "prefer": sorted(prefer),
        "dinner": dinner,
        "budget": budget,
        "first_day": valid_day(answers.get("premiere")),
        "end": end,
        "names": (answers.get("prenoms") or "").strip()[:80] or None,
    }


def valid_day(value: Any) -> str | None:
    """A day as the page sends it (2026-10-09), or None."""
    try:
        return date.fromisoformat(value).isoformat() if isinstance(value, str) and len(value) == 10 else None
    except ValueError:
        return None


ENVIE_KEYS = {envie["value"]: envie for envie in ENVIES}
OCCASION_KEYS = {occasion["value"]: occasion for occasion in OCCASIONS}


MAX_VIBES = 5


def _late(hour: str) -> str:
    """An hour as the evening sees it: 03:30 comes after 23:30."""
    return f"{int(hour[:2]) + 24}{hour[2:]}" if hour < "12:00" else hour


def evening(
    profile: dict[str, Any], envies: list[str] | None = None, occasion: str | None = None, dinner: bool | None = None,
) -> dict[str, Any]:
    """One evening's settings: its wishes and occasion over the profile, which keeps refusals, budget and tastes.

    `dinner`: whether the couple eats during the evening, asked each time; it wins over the profile and the wishes.
    Not said (None): a dinner when the profile, a wish or the occasion calls for one, and maybe one otherwise.
    """
    wishes = [ENVIE_KEYS[e] for e in dict.fromkeys(envies or []) if e in ENVIE_KEYS][:MAX_ENVIES] or [ENVIES[0]]
    event = OCCASION_KEYS.get(occasion or "rien", OCCASION_KEYS["rien"])
    # Each wish's vibes, the profile's for "nous" and "surprise"; taken in turn so that every wish has its share.
    lists = [(["insolite"] if w["value"] == "surprise" else []) + (w["vibes"] or list(profile["vibes"])) for w in wishes]
    turns = [vibes[i] for i in range(max(map(len, lists))) for vibes in lists if i < len(vibes)]
    vibes = list(dict.fromkeys(turns + event["vibes"]))[:MAX_VIBES]
    # A wish's refusals give way to what another wish asks for (cocooning then party: the club stays).
    wanted = set().union(*(VIBES[v]["tags"] | VIBES[v]["categories"] for v in vibes))
    avoid = set().union(*(w.get("avoid") or [] for w in wishes)) - wanted
    ends = [w["end"] for w in wishes if "end" in w]
    return {
        "envies": [w["value"] for w in wishes],
        "occasion": event["value"],
        "vibes": vibes,
        "audace": min(1.0, profile["audace"] + max(w.get("audace", 0) for w in wishes)),
        "avoid": sorted(set(profile["avoid"]) | avoid),
        "dinner": dinner if dinner is not None else profile["dinner"] or any(w.get("dinner") for w in wishes) or bool(event.get("dinner")),
        "no_dinner": dinner is False,
        "start": min((w["start"] for w in wishes if "start" in w), default=DEFAULT_START),
        "end": max(ends, key=_late) if ends else profile.get("end") or DEFAULT_END,
    }


def requests_for(
    profile: dict[str, Any], days: list[date] | None = None, envies: list[str] | None = None, occasion: str | None = None,
    dinner: bool | None = None,
) -> list[parcours.Request]:
    """The evenings to plan for a profile and wishes: the days given, its first outing, else the next Friday and Saturday."""
    if not days:
        if profile.get("first_day"):
            days = [date.fromisoformat(profile["first_day"])]
        else:
            today = date.today()
            friday = today + timedelta(days=(4 - today.weekday()) % 7)
            days = [friday, friday + timedelta(days=1)]
    night = evening(profile, envies, occasion, dinner)
    requests = []
    for day in days:
        begin, finish = parcours.window(day, night["start"], night["end"])
        requests.append(parcours.Request(
            day, profile["budget"], begin, finish, night["vibes"],
            audace=night["audace"], avoid=set(night["avoid"]), prefer=set(profile["prefer"]), dinner=night["dinner"],
            no_dinner=night["no_dinner"],
        ))
    return requests


def new_id() -> str:
    return secrets.token_urlsafe(6)


_ID = re.compile(r"^[\w-]{4,20}$")
# /api/parcours/<page>/routes/<index>[/steps/<position>]: draw a route, or one of its steps, again.
_REDO = re.compile(r"^/api/parcours/(?P<name>[\w-]+)/routes/(?P<route>\d+)(?:/steps/(?P<step>\d+))?$")
BASE_MINUTES = 15


def make_handler(db_path: Path, checks: int, warm: bool = False) -> type[BaseHTTPRequestHandler]:
    # One composition at a time: it checks booking engines and writes the page.
    composing = threading.Lock()
    # The activities take seconds to load: loaded when the server starts, then again in the background
    # when a quarter of an hour old, the evening being composed meanwhile with the previous ones.
    loaded: dict[str, Any] = {}
    loading = threading.Lock()

    def reload() -> None:
        with LocalStore(db_path) as store:
            fresh = parcours.Base.load(store)
        with loading:
            loaded.update(at=clock.monotonic(), base=fresh, refreshing=False)

    def base(store: LocalStore) -> parcours.Base:
        with loading:
            if "base" not in loaded:
                loaded.update(at=clock.monotonic(), base=parcours.Base.load(store), refreshing=False)
            elif clock.monotonic() - loaded["at"] > BASE_MINUTES * 60 and not loaded["refreshing"]:
                loaded["refreshing"] = True
                threading.Thread(target=reload, daemon=True).start()
            return loaded["base"]

    def warm_up() -> None:
        # Holds the lock while loading: a composition asked meanwhile waits for it rather than loading again.
        with LocalStore(db_path) as store:
            base(store)

    if warm:
        threading.Thread(target=warm_up, daemon=True).start()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path in STATIC:
                name, content_type = STATIC[path]
                self._send(HTTPStatus.OK, RESOURCES.joinpath(name).read_bytes(), content_type)
            elif path == "/api/quiz":
                vibes = {key: v["label"] for key, v in VIBES.items()}
                self._send_json(HTTPStatus.OK, {"questions": QUESTIONS, "vibes": vibes})
            elif path == "/api/soiree":
                self._send_json(HTTPStatus.OK, {"envies": ENVIES, "occasions": OCCASIONS, "max": MAX_ENVIES})
            elif path.startswith("/api/profiles/") and _ID.match(path.rsplit("/", 1)[1]):
                with LocalStore(db_path) as store:
                    found = store.get_profile(path.rsplit("/", 1)[1])
                self._send_json(HTTPStatus.OK if found else HTTPStatus.NOT_FOUND, found or {"error": "profil inconnu"})
            elif re.match(r"^/parcours/[\w-]+\.html$", path):
                page = parcours.OUTPUT_DIR / path.removeprefix("/parcours/")
                if page.exists():
                    self._send(HTTPStatus.OK, page.read_bytes(), "text/html; charset=utf-8")
                else:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "introuvable"})
            elif re.match(r"^/images/\w+\.\w+$", path) and (image := images.DIRECTORY / path.removeprefix("/images/")).exists():
                self._send(HTTPStatus.OK, image.read_bytes(), images.MEDIA_TYPES.get(image.suffix, "application/octet-stream"))
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "introuvable"})

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            # Requiring JSON forces a CORS preflight, so other sites cannot post here.
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                return self._send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "JSON attendu"})
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            except ValueError:
                return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "JSON invalide"})
            if path == "/api/profiles":
                answers = body.get("answers") if isinstance(body.get("answers"), dict) else {}
                profile_id, profile = new_id(), profile_from(answers)
                with LocalStore(db_path) as store:
                    store.save_profile(profile_id, answers, profile)
                return self._send_json(HTTPStatus.CREATED, {"id": profile_id, "profile": profile})
            if path == "/api/soirees":
                return self._compose(body)
            if redo := _REDO.match(path):
                return self._redo(redo["name"], int(redo["route"]), None if redo["step"] is None else int(redo["step"]))
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "introuvable"})

        def _compose(self, body: dict[str, Any]) -> None:
            """An evening's routes: its wishes, occasion and day, with the profile given or default settings."""
            asked = body.get("envies") if isinstance(body.get("envies"), list) else []
            envies = [e for e in dict.fromkeys(e for e in asked if isinstance(e, str)) if e in ENVIE_KEYS][:MAX_ENVIES]
            if not envies:
                return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "au moins une envie"})
            if not isinstance(body.get("diner"), bool):
                return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "dîner ou pas ?"})
            occasion = body.get("occasion") if body.get("occasion") in OCCASION_KEYS else None
            day = valid_day(body.get("day"))
            days = [date.fromisoformat(day)] if day else None
            profile_id = body.get("profile")
            with LocalStore(db_path) as store:
                if profile_id is None:
                    profile = profile_from({})
                elif isinstance(profile_id, str) and _ID.match(profile_id) and (found := store.get_profile(profile_id)):
                    profile = found["profile"]
                else:
                    return self._send_json(HTTPStatus.NOT_FOUND, {"error": "profil inconnu"})
                name = f"soiree-{profile_id or 'libre'}-{'-'.join(envies)}-{'diner' if body['diner'] else 'sans-diner'}"
                with composing:
                    routes, page = parcours.generate(
                        store, requests_for(profile, days, envies, occasion, body["diner"]), count=3, checks=checks, name=name,
                        base=base(store), name_later=True,
                    )
            self._send_json(HTTPStatus.OK, {"url": f"/parcours/{page.name}", "count": len(routes)})

        def _redo(self, name: str, index: int, position: int | None) -> None:
            """Another route in place of route `index`, or another activity at its step `position`."""
            with LocalStore(db_path) as store, composing:
                error = parcours.regenerate(store, base(store), name, index, position, checks=min(checks, 10))
            if error:
                return self._send_json(HTTPStatus.CONFLICT, {"error": error})
            self._send_json(HTTPStatus.OK, {"url": f"/parcours/{name}.html"})

        def _send_json(self, code: HTTPStatus, payload: Any) -> None:
            self._send(code, json.dumps(payload, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def _send(self, code: HTTPStatus, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Questionnaire client : profil du couple, puis ses soirées")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--db", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--checks", type=int, default=30, help="vérifications de disponibilité en direct par soirée composée")
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    # A Windows console cannot show every character (✓, ✗): replace them rather than fail.
    sys.stdout.reconfigure(errors="replace")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.db, args.checks, warm=True))
    url = f"http://127.0.0.1:{args.port}"
    print(f"Questionnaire : {url}")
    if not args.no_open:
        webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__":
    main()
