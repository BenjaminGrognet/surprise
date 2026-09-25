"""Client questionnaire: a short, playful quiz that draws the couple's profile, then their evenings.

Each answer weighs on the vibes (surprise.tags.VIBES) and sets the couple's
appetite for the unusual (audace), what they refuse, the music they like, the
budget and the hours. The profile keeps the weighted vibes, the main ones, a
persona to tell them who they are ("Les Explorateurs"), and is stored with the
answers (table profiles). From it, surprise.parcours composes their evenings.

    uv run python -m surprise.quiz            # http://127.0.0.1:8001

Served on 127.0.0.1 with the standard library, like the moderation page.
"""

import argparse
import json
import re
import secrets
import sys
import threading
import webbrowser
from datetime import date, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from surprise import parcours
from surprise.local_store import DEFAULT_PATH, LocalStore
from surprise.tags import VIBES

PAGE = files("surprise").joinpath("quiz.html")

# id, question, hint, kind ("single", "multi", "scale", "when", "text"), options.
# An option: value, label, emoji, and what it does: vibe weights, audace, avoid, prefer, end, budget, dinner.
QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "occasion", "kind": "single",
        "question": "Qu'est-ce qu'on fête ?", "hint": "Il n'y a pas de mauvaise raison de sortir.",
        "options": [
            {"value": "envie", "label": "Rien, juste l'envie", "emoji": "✨", "vibes": {"insolite": 1}},
            {"value": "anniversaire", "label": "Un anniversaire", "emoji": "🎂", "vibes": {"romantique": 2, "savourer": 1}, "dinner": True},
            {"value": "debut", "label": "Nos premiers rendez-vous", "emoji": "🌱", "vibes": {"rire": 1, "defi": 1}, "avoid": ["dans_le_noir"]},
            {"value": "retrouvailles", "label": "Se retrouver, enfin", "emoji": "🫶", "vibes": {"detente": 2, "romantique": 1}},
            {"value": "grande", "label": "Une grande occasion", "emoji": "💍", "vibes": {"romantique": 3, "emerveiller": 1}, "dinner": True, "audace": 0.1},
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
            {"value": "deja", "label": "On aura déjà dîné", "emoji": "✅", "vibes": {}},
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
        "question": "La fin de soirée idéale ?", "hint": None,
        "options": [
            {"value": "tot", "label": "Rentrer avant minuit", "emoji": "🌙", "end": "23:30"},
            {"value": "verre", "label": "Un dernier verre", "emoji": "🍸", "end": "00:30", "vibes": {"savourer": 1}},
            {"value": "danser", "label": "Danser jusqu'au bout de la nuit", "emoji": "🌃", "end": "03:30", "vibes": {"fete": 3}},
        ],
    },
    {
        "id": "eviter", "kind": "multi",
        "question": "Ce que vous préférez éviter", "hint": "Tout est permis, sauf ça.",
        "options": [
            {"value": "noir", "label": "Le noir complet", "emoji": "🌑", "avoid": ["dans_le_noir"]},
            {"value": "peur", "label": "Les frissons, la peur", "emoji": "😱", "avoid": ["frisson", "souterrain", "murder_party"]},
            {"value": "effort", "label": "Transpirer", "emoji": "🥵", "avoid": ["sport", "jeu_actif", "defouloir"]},
            {"value": "alcool", "label": "L'alcool", "emoji": "🚱", "avoid": ["mixologie", "vin", "cocktails", "vins nature"]},
            {"value": "scene", "label": "Être mis en scène", "emoji": "🎭", "avoid": ["interactif", "karaoke"]},
            {"value": "eau", "label": "Les bateaux", "emoji": "⛵", "avoid": ["sur_l_eau"]},
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
    {"id": "quand", "kind": "when", "question": "Quand sortez-vous ?", "hint": "Le jour et l'heure du premier rendez-vous de la soirée."},
    {"id": "prenoms", "kind": "text", "question": "Et vous êtes ?", "hint": "Vos prénoms, pour personnaliser vos soirées (facultatif)."},
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
DEFAULT_START = "19:00"
DEFAULT_END = "00:30"


def profile_from(answers: dict[str, Any]) -> dict[str, Any]:
    """The couple's profile from their answers: weighted vibes, main vibes, persona, audace, refusals, budget, hours."""
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
    when = answers.get("quand") or {}
    return {
        "vibes": main,
        "weights": {v: weights[v] for v in ranked},
        "persona": {"name": persona[1], "text": persona[2]},
        "audace": audace,
        "avoid": sorted(avoid),
        "prefer": sorted(prefer),
        "dinner": dinner,
        "budget": budget,
        "day": when.get("day"),
        "start": when.get("start") or DEFAULT_START,
        "end": end,
        "names": (answers.get("prenoms") or "").strip()[:80] or None,
    }


def requests_for(profile: dict[str, Any], days: list[date] | None = None) -> list[parcours.Request]:
    """The evenings to plan for a profile: its date, else the next Friday and Saturday."""
    if not days:
        if profile.get("day"):
            days = [date.fromisoformat(profile["day"])]
        else:
            today = date.today()
            friday = today + timedelta(days=(4 - today.weekday()) % 7)
            days = [friday, friday + timedelta(days=1)]
    requests = []
    for day in days:
        begin, finish = parcours.window(day, profile["start"], profile["end"])
        requests.append(parcours.Request(
            day, profile["budget"], begin, finish, profile["vibes"],
            audace=profile["audace"], avoid=set(profile["avoid"]), prefer=set(profile["prefer"]), dinner=profile["dinner"],
        ))
    return requests


def new_id() -> str:
    return secrets.token_urlsafe(6)


_ID = re.compile(r"^[\w-]{4,20}$")


def make_handler(db_path: Path, checks: int) -> type[BaseHTTPRequestHandler]:
    # One composition at a time: it checks booking engines and writes the page.
    composing = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/":
                self._send(HTTPStatus.OK, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/quiz":
                vibes = {key: v["label"] for key, v in VIBES.items()}
                self._send_json(HTTPStatus.OK, {"questions": QUESTIONS, "vibes": vibes})
            elif path.startswith("/api/profiles/") and _ID.match(path.rsplit("/", 1)[1]):
                with LocalStore(db_path) as store:
                    found = store.get_profile(path.rsplit("/", 1)[1])
                self._send_json(HTTPStatus.OK if found else HTTPStatus.NOT_FOUND, found or {"error": "profil inconnu"})
            elif path.startswith("/parcours/") and re.match(r"^/parcours/profil-[\w-]+\.html$", path):
                page = parcours.OUTPUT_DIR / path.removeprefix("/parcours/")
                if page.exists():
                    self._send(HTTPStatus.OK, page.read_bytes(), "text/html; charset=utf-8")
                else:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "introuvable"})
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
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[:2] == ["api", "profiles"] and parts[3] == "parcours" and _ID.match(parts[2]):
                return self._compose(parts[2])
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "introuvable"})

        def _compose(self, profile_id: str) -> None:
            with LocalStore(db_path) as store:
                found = store.get_profile(profile_id)
                if not found:
                    return self._send_json(HTTPStatus.NOT_FOUND, {"error": "profil inconnu"})
                with composing:
                    routes, page = parcours.generate(
                        store, requests_for(found["profile"]), count=3, checks=checks, name=f"profil-{profile_id}",
                    )
            self._send_json(HTTPStatus.OK, {"url": f"/parcours/{page.name}", "count": len(routes)})

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
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.db, args.checks))
    url = f"http://127.0.0.1:{args.port}"
    print(f"Questionnaire : {url}")
    if not args.no_open:
        webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__":
    main()
