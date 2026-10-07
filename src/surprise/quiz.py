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

An evening is a couple's (Secret Date) or a band of friends' (Secret Squad,
?formule=squad): 2 to 10, its own wishes, occasions and budgets per person; no profile, everything
from the order of the evening, what the band never wants included.

    uv run python -m surprise.quiz            # http://127.0.0.1:8001

One site: the app's web build (app/dist, `npm run build:web` in app/: the home,
/profil, /soiree, /compte, /historique), the API it calls (/api/…) and the
moderation page (/admin, from surprise.admin). Served on 127.0.0.1 with the
standard library.
"""

import argparse
import json
import mimetypes
import re
import secrets
import sys
import threading
import time as clock
import webbrowser
from datetime import date, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from surprise import admin, images, parcours
from surprise.local_store import LocalStore, open_store
from surprise.genres import GENRES
from surprise.tags import VIBES

# The site is the app itself, built for the web: one front for the phone and the browser.
WEB = Path(__file__).resolve().parents[2] / "app" / "dist"
# Not mimetypes.guess_type: on Windows it reads the registry, which may call a script text/plain.
TYPES = mimetypes.MimeTypes()


def web_file(path: str) -> Path | None:
    """The app's web build file at this address: / is index.html, /soiree is soiree.html."""
    name = unquote(path).strip("/") or "index"
    for file in (WEB / name, WEB / f"{name}.html"):
        if file.is_file() and file.resolve().is_relative_to(WEB):
            return file
    return None

# A soirée-type budget (profile) that the couple can also adjust for one particular evening (/soiree).
BUDGET_OPTIONS: list[dict[str, Any]] = [
    {"value": "doux", "label": "Moins de 60 €", "desc": "Les bons plans", "icon": "pieces", "emoji": "🪙", "budget": 60},
    {"value": "moyen", "label": "60 à 120 €", "desc": "Le juste équilibre", "icon": "portefeuille", "emoji": "💶", "budget": 120},
    {"value": "genereux", "label": "120 à 200 €", "desc": "Se faire plaisir", "icon": "carte", "emoji": "💳", "budget": 200},
    {"value": "folie", "label": "On ne compte pas", "desc": "Les grandes occasions", "icon": "diamant", "emoji": "💎", "budget": 350},
]
# Asked each time an evening is composed (/soiree), not in the profile: when it starts and ends.
START_OPTIONS: list[dict[str, Any]] = [
    {"value": "normal", "label": "À l'heure habituelle", "icon": "horloge", "emoji": "🕖", "start": "19:00"},
    {"value": "tot", "label": "On commence plus tôt", "icon": "couchant", "emoji": "🌇", "start": "17:00"},
]
END_OPTIONS: list[dict[str, Any]] = [
    {"value": "tot", "label": "Avant minuit", "icon": "lune", "emoji": "🌙", "end": "23:30"},
    {"value": "verre", "label": "Sur un dernier verre", "icon": "verre", "emoji": "🍸", "end": "00:30"},
    {"value": "danser", "label": "Au bout de la nuit", "icon": "disco", "emoji": "🌃", "end": "03:30"},
]

# The profile's questions: what lasts from one evening to the next — no hour or meal, asked
# each time instead (/soiree). id, question, hint, kind ("single", "multi", "scale", "date", "text"), min/max
# (multi), options. An option: value, label, desc and icon (the app's velvet card: option-card.tsx), emoji
# (where there's no icon: /soiree), and what it does: vibe weights, audace, avoid, prefer, genre (surprise.genres), budget.
QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "couple", "kind": "single",
        "question": "Où en est votre histoire ?", "hint": "Pour viser juste dès la première soirée.",
        "options": [
            {"value": "debut", "label": "On se découvre", "desc": "Les premiers rendez-vous", "icon": "pousse", "emoji": "🌱",
             "vibes": {"rire": 1, "defi": 1}, "avoid": ["dans_le_noir"]},
            {"value": "complices", "label": "Complices", "desc": "Depuis un moment déjà", "icon": "coeur", "emoji": "🤝",
             "vibes": {"rire": 1, "insolite": 1}},
            {"value": "installes", "label": "Installés", "desc": "Envie de pimenter", "icon": "flamme", "emoji": "🌶️",
             "vibes": {"insolite": 1, "romantique": 1, "coquin": 1}},
            {"value": "longue", "label": "Une longue histoire", "desc": "À célébrer", "icon": "infini", "emoji": "💞",
             "vibes": {"romantique": 2, "savourer": 1}},
        ],
    },
    {
        "id": "debut_soiree", "kind": "single",
        "question": "Votre soirée idéale commence par…", "hint": "Le premier instant donne le ton.",
        "options": [
            {"value": "terrasse", "label": "Un verre au couchant", "desc": "En terrasse, au soleil", "icon": "couchant", "emoji": "🌇",
             "vibes": {"savourer": 1, "flaner": 1, "romantique": 1}},
            {"value": "culture", "label": "Un lieu chargé d'histoire", "desc": "Musées, monuments, secrets", "icon": "monument", "emoji": "🏛️",
             "vibes": {"cultiver": 2}},
            {"value": "defi", "label": "Un défi à deux", "desc": "Jeu, énigme, compétition", "icon": "cible", "emoji": "🧩",
             "vibes": {"defi": 2}},
            {"value": "cocon", "label": "Rien qu'à nous", "desc": "Un moment hors du temps", "icon": "bougie", "emoji": "🕯️",
             "vibes": {"romantique": 2, "detente": 1}},
            {"value": "creer", "label": "Les mains à la pâte", "desc": "Créer, cuisiner, façonner", "icon": "pinceau", "emoji": "🎨",
             "vibes": {"creer": 2}},
        ],
    },
    {
        "id": "energie", "kind": "scale",
        "question": "Plutôt cocooning ou dancefloor ?", "hint": "Du canapé à la piste de danse : où vous situez-vous ?",
        "options": [
            {"value": 1, "label": "Cocooning", "desc": "On se pose", "icon": "lune", "emoji": "🛋️", "vibes": {"detente": 2}},
            {"value": 2, "label": "Calme", "desc": "Sans hâte", "icon": "tasse", "emoji": "🍵", "vibes": {"detente": 1, "cultiver": 1}},
            {"value": 3, "label": "Actif", "desc": "On bouge un peu", "icon": "boussole", "emoji": "🚶", "vibes": {"flaner": 1}},
            {"value": 4, "label": "Festif", "desc": "Ça s'anime", "icon": "etincelles", "emoji": "🕺", "vibes": {"bouger": 1, "musique": 1}},
            {"value": 5, "label": "Dancefloor", "desc": "On ne tient pas en place", "icon": "disco", "emoji": "🪩",
             "vibes": {"fete": 2, "bouger": 1}},
        ],
    },
    {
        "id": "reussie", "kind": "multi", "min": 1, "max": 2,
        "question": "Une soirée réussie, c'est quand…", "hint": "Deux réponses au plus pour cibler vos désirs.",
        # icon + desc: shown as a grid of cards with a gold line icon (app: option-card.tsx).
        "options": [
            {"value": "rire", "label": "Éclats de rire", "desc": "Lâcher-prise total", "icon": "rires", "emoji": "😂", "vibes": {"rire": 2}},
            {"value": "yeux", "label": "Émerveillement", "desc": "En prendre plein les yeux", "icon": "yeux", "emoji": "🤩", "vibes": {"emerveiller": 2}},
            {"value": "appris", "label": "Curiosité", "desc": "Apprendre ou découvrir", "icon": "esprit", "emoji": "🧠", "vibes": {"cultiver": 2}},
            {"value": "mains", "label": "Un souvenir physique", "desc": "Repartir avec un objet", "icon": "objet", "emoji": "🏺", "vibes": {"creer": 2}},
            {"value": "musique", "label": "Vibration musicale", "desc": "Portés par le rythme", "icon": "musique", "emoji": "🎷", "vibes": {"musique": 2}},
            {"value": "frissons", "label": "Frissons secrets", "desc": "Sensations & mystère", "icon": "frissons", "emoji": "👻", "vibes": {"frisson": 2}},
        ],
    },
    {
        "id": "audace", "kind": "single",
        "question": "Jusqu'où osez-vous ?", "hint": "Pour savoir à quel point vous surprendre.",
        "options": [
            {"value": "classique", "label": "Du classique", "desc": "Des valeurs sûres", "icon": "ancre", "emoji": "🎩", "audace": 0.1},
            {"value": "pointe", "label": "Une pointe d'originalité", "desc": "Hors des sentiers battus", "icon": "plume", "emoji": "🌶️",
             "audace": 0.4, "vibes": {"insolite": 1}},
            {"value": "surprenez", "label": "Surprenez-nous", "desc": "On vous fait confiance", "icon": "cadeau", "emoji": "🎁",
             "audace": 0.7, "vibes": {"insolite": 2}},
            {"value": "fou", "label": "Plus c'est fou, mieux c'est", "desc": "Aucune limite", "icon": "fusee", "emoji": "🚀",
             "audace": 1.0, "vibes": {"insolite": 3}},
        ],
    },
    {
        # The genres filter the concerts (surprise.genres); classical ones stay possible, ticked or not.
        "id": "musique", "kind": "multi",
        "question": "Vos musiques préférées ?",
        "hint": "Autant de genres que vous voulez, ou aucun pour tout garder ouvert. Le classique aux chandelles reste possible.",
        "options": [
            {"value": "rock", "label": "Pop, rock & indé", "icon": "enceinte", "emoji": "🎸", "genre": "rock", "vibes": {"musique": 1}},
            {"value": "chanson", "label": "Chanson & variété", "icon": "micro", "emoji": "🎤", "genre": "chanson", "vibes": {"musique": 1}},
            {"value": "jazz", "label": "Jazz & blues", "icon": "note", "emoji": "🎺", "genre": "jazz", "vibes": {"musique": 1}},
            {"value": "soul", "label": "Soul, funk & R&B", "icon": "vinyle", "emoji": "🪩", "genre": "soul", "vibes": {"musique": 1}},
            {"value": "rap", "label": "Rap & hip-hop", "icon": "radio", "emoji": "🎧", "genre": "rap", "vibes": {"musique": 1}},
            {"value": "electro", "label": "Électro & techno", "icon": "casque", "emoji": "🎛️", "genre": "electro", "vibes": {"fete": 1}},
            {"value": "latino", "label": "Latino, afro & reggae", "icon": "tambour", "emoji": "💃", "genre": "latino",
             "vibes": {"fete": 1, "bouger": 1}},
            {"value": "metal", "label": "Metal & hard rock", "icon": "eclair", "emoji": "🤘", "genre": "metal", "vibes": {"musique": 1}},
            {"value": "classique", "label": "Classique & opéra", "icon": "piano", "emoji": "🎻", "genre": "classique",
             "prefer": ["chandelles"], "vibes": {"musique": 1, "romantique": 1}},
        ],
    },
    {
        "id": "eviter", "kind": "multi",
        "question": "Ce que vous ne voulez jamais", "hint": "Aucune soirée ne vous le proposera. Autant de réponses que vous voulez.",
        "options": [
            {"value": "maillot", "label": "Le maillot de bain", "desc": "Spa, piscine, flottaison", "icon": "vagues", "emoji": "🩱",
             "avoid": ["spa", "flottaison", "baignade"]},
            {"value": "noir", "label": "Le noir complet", "desc": "Dîners à l'aveugle", "icon": "oeil_ferme", "emoji": "🌑",
             "avoid": ["dans_le_noir"]},
            {"value": "peur", "label": "La peur", "desc": "Frissons, souterrains", "icon": "fantome", "emoji": "😱",
             "avoid": ["frisson", "souterrain", "murder_party"]},
            {"value": "effort", "label": "Transpirer", "desc": "Sport, jeux physiques", "icon": "goutte", "emoji": "🥵",
             "avoid": ["sport", "jeu_actif", "defouloir", "sensations"]},
            {"value": "alcool", "label": "L'alcool", "desc": "Dégustations, cocktails", "icon": "verre", "emoji": "🚱",
             "avoid": ["mixologie", "vin", "cocktails", "vins nature"]},
            {"value": "scene", "label": "Être mis en scène", "desc": "Spectacles interactifs", "icon": "projecteur", "emoji": "🎭",
             "avoid": ["interactif", "karaoke"]},
            {"value": "danser", "label": "Danser", "desc": "Même un peu", "icon": "disco", "emoji": "🙅", "avoid": ["danse"]},
            {"value": "assis", "label": "Rester assis", "desc": "Deux heures sans bouger", "icon": "fauteuil", "emoji": "🪑",
             "avoid": ["theatre", "cinema", "lecture", "comedie_musicale"]},
            {"value": "eau", "label": "Les bateaux", "desc": "Croisières, péniches", "icon": "voilier", "emoji": "⛵",
             "avoid": ["sur_l_eau"]},
            {"value": "ecrans", "label": "Les écrans", "desc": "Réalité virtuelle, jeux vidéo", "icon": "ecran", "emoji": "🥽",
             "avoid": ["jeu_video"]},
            {"value": "coquin", "label": "Le coquin", "desc": "Effeuillage, cabaret osé", "icon": "levres", "emoji": "🙈",
             "avoid": ["coquin"]},
        ],
    },
    {
        "id": "budget", "kind": "single",
        "question": "Votre budget pour deux ?", "hint": "Pour une soirée type, hors transport ; ajustable à chaque soirée.",
        "options": BUDGET_OPTIONS,
    },
    {"id": "premiere", "kind": "date", "question": "Votre première sortie ?", "hint": "Le jour qui vous tente ; l'envie de la soirée, on vous la demandera juste avant."},
    {"id": "prenoms", "kind": "text", "question": "Et vous êtes ?", "hint": "Vos prénoms, pour personnaliser vos soirées (facultatif)."},
]

# The wishes of one evening, MAX_ENVIES at most, asked each time: they set that evening's vibes and hours,
# the profile the rest. value, label, emoji, vibes (none: the profile's), and optionally start, end, dinner,
# audace, avoid (dropped when another wish of the evening asks for it: party and cocooning go together).
MAX_ENVIES = 3
ENVIES: list[dict[str, Any]] = [
    {"value": "nous", "label": "Fidèles à nous-mêmes", "icon": "ancre", "emoji": "💫", "vibes": []},
    {"value": "fete", "label": "Faire la fête", "icon": "disco", "emoji": "🪩", "vibes": ["fete", "musique"], "start": "20:00", "end": "03:30"},
    {"value": "cocooning", "label": "Cocooning", "icon": "fauteuil", "emoji": "🧸", "vibes": ["detente", "romantique", "savourer"], "end": "23:30",
     "avoid": ["nuit", "electro", "danse", "sport", "jeu_actif", "defouloir", "grande_salle", "frisson"]},
    {"value": "romantique", "label": "Romantique", "icon": "bougie", "emoji": "🕯️", "vibes": ["romantique", "savourer", "emerveiller"], "dinner": True},
    {"value": "rire", "label": "Rire aux éclats", "icon": "rires", "emoji": "😂", "vibes": ["rire", "defi"]},
    {"value": "jouer", "label": "Jouer, relever un défi", "icon": "cible", "emoji": "🧩", "vibes": ["defi", "bouger"]},
    {"value": "curieux", "label": "Apprendre, s'émerveiller", "icon": "monument", "emoji": "🏛️", "vibes": ["cultiver", "emerveiller"]},
    {"value": "creer", "label": "Créer de nos mains", "icon": "pinceau", "emoji": "🎨", "vibes": ["creer", "savourer"]},
    {"value": "gourmand", "label": "Se régaler", "icon": "couvert", "emoji": "🍽️", "vibes": ["savourer"], "dinner": True},
    {"value": "musique", "label": "Vibrer en musique", "icon": "musique", "emoji": "🎷", "vibes": ["musique", "emerveiller"]},
    {"value": "air", "label": "Prendre l'air", "icon": "boussole", "emoji": "🌿", "vibes": ["flaner", "savourer"], "start": "18:30"},
    {"value": "pimenter", "label": "Pimenter la soirée", "icon": "flamme", "emoji": "🌶️", "vibes": ["coquin", "romantique"], "start": "20:00"},
    {"value": "frissons", "label": "Frissonner", "icon": "frissons", "emoji": "👻", "vibes": ["frisson", "insolite"]},
    {"value": "surprise", "label": "Surprenez-nous", "icon": "cadeau", "emoji": "🎁", "vibes": [], "audace": 0.3},
]

# What the evening celebrates, if anything: added to its wishes.
OCCASIONS: list[dict[str, Any]] = [
    {"value": "anniversaire", "label": "Un anniversaire", "icon": "gateau", "emoji": "🎂", "vibes": ["romantique"], "dinner": True},
    {"value": "retrouvailles", "label": "Des retrouvailles", "icon": "coeur", "emoji": "🫶", "vibes": ["romantique"]},
    {"value": "grande", "label": "Une grande occasion", "icon": "diamant", "emoji": "💍", "vibes": ["romantique", "emerveiller"], "dinner": True},
    {"value": "rien", "label": "Rien, juste l'envie", "icon": "etincelles", "emoji": "✨", "vibes": []},
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
# The mood cards of /soiree, from the calmest to the wildest: each is one of the wishes, the others the "secret options".
MOODS = ["cocooning", "romantique", "nous", "curieux", "surprise"]

# Secret Squad: an evening for a band of friends (a hen or stag party, a birthday, a farewell drink…), with its own
# wishes, occasions and budgets, per person as a band counts. No profile, nor the account's votes: everything comes
# from the order of the evening (squad_profile), what the band never wants included; only the evenings done still count.
# From two: an evening out with a friend is no date. Ten at most: of 48 activities bookable online (checked for
# 2026-10-16), 27 seated two, 26 six, 16 ten, only 9 twelve.
SQUAD_PERSONNES = {"min": 2, "max": 10, "default": 6}
SQUAD_BUDGET_OPTIONS: list[dict[str, Any]] = [
    {"value": "doux", "label": "Moins de 30 €", "desc": "Par personne, les bons plans", "icon": "pieces", "emoji": "🪙", "budget": 30},
    {"value": "moyen", "label": "30 à 60 €", "desc": "Par personne, l'équilibre", "icon": "portefeuille", "emoji": "💶", "budget": 60},
    {"value": "genereux", "label": "60 à 100 €", "desc": "Par personne, on se lâche", "icon": "carte", "emoji": "💳", "budget": 100},
    {"value": "folie", "label": "On ne compte pas", "desc": "Par personne, la soirée de l'année", "icon": "diamant", "emoji": "💎", "budget": 180},
]
SQUAD_BUDGET = 60  # per person, when none is chosen


def _wish(value: str, **changes: Any) -> dict[str, Any]:
    """A couple's wish, as a band's (its words changed, if need be)."""
    return next(envie for envie in ENVIES if envie["value"] == value) | changes


SQUAD_ENVIES: list[dict[str, Any]] = [
    {"value": "trinquer", "label": "Trinquer", "icon": "verre", "emoji": "🍻", "vibes": ["savourer", "rire"], "start": "18:30"},
    _wish("fete"),
    _wish("rire", label="Rire aux larmes"),
    _wish("jouer", label="Se défier entre potes"),
    {"value": "chanter", "label": "Chanter à tue-tête", "icon": "micro", "emoji": "🎤", "vibes": ["fete", "rire"], "prefer": ["karaoke", "quiz"]},
    _wish("frissons"),
    _wish("gourmand"),
    _wish("musique"),
    _wish("creer", label="Créer ensemble"),
    _wish("curieux"),
    _wish("air"),
    # A couple's surprise takes its profile's vibes; a band has none, so its own.
    _wish("surprise", vibes=["rire", "defi"]),
]
SQUAD_MOODS = ["trinquer", "rire", "jouer", "chanter", "fete"]
# What the band never wants, asked with the order: the quiz's refusals, the couple's profile not applying.
SQUAD_EVITER: list[dict[str, Any]] = next(q for q in QUESTIONS if q["id"] == "eviter")["options"]
# The vibes said as a band says them (a kept evening's moods, in its history); the others keep their words.
SQUAD_VIBE_LABELS = {
    "bouger": "Se dépenser ensemble", "defi": "Défis entre potes", "rire": "Fous rires", "creer": "Créer ensemble",
    "savourer": "Trinquer et se régaler", "detente": "Décompresser", "fete": "Mettre le feu", "frisson": "Se faire peur",
    "romantique": "Paillettes", "coquin": "Pimenter la soirée",
}
SQUAD_OCCASIONS: list[dict[str, Any]] = [
    {"value": "evjf", "label": "Un EVJF ou un EVG", "icon": "couronne", "emoji": "👑", "vibes": ["fete", "rire"], "prefer": ["evjf"]},
    {"value": "anniversaire", "label": "Un anniversaire", "icon": "gateau", "emoji": "🎂", "vibes": ["fete"], "dinner": True},
    {"value": "depart", "label": "Un pot de départ", "icon": "verre", "emoji": "🥂", "vibes": ["savourer", "rire"]},
    {"value": "retrouvailles", "label": "Des retrouvailles", "icon": "bande", "emoji": "🫂", "vibes": ["savourer", "rire"]},
    {"value": "equipe", "label": "Une sortie d'équipe", "icon": "cible", "emoji": "🏆", "vibes": ["defi", "rire"]},
    {"value": "rien", "label": "Rien, juste l'envie", "icon": "etincelles", "emoji": "✨", "vibes": []},
]


def squad_profile(eviter: list[str] | None = None) -> dict[str, Any]:
    """The band's settings, from its order alone (no couple's profile): what a group shares, a little daring, the usual
    budget, and what it said it never wants (`eviter`: SQUAD_EVITER values)."""
    return profile_from({"eviter": eviter or []}) | {"vibes": ["rire", "fete", "savourer", "defi"], "budget": SQUAD_BUDGET * SQUAD_PERSONNES["default"]}


def profile_from(answers: dict[str, Any]) -> dict[str, Any]:
    """The couple's profile from their answers: weighted vibes, main vibes, persona, audace, refusals, a typical budget."""
    weights = {key: 0.0 for key in VIBES}
    audace, avoid, prefer, genres = 0.5, set(), set(), set()
    budget = 120
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
            genres |= {option["genre"]} if "genre" in option else set()
            budget = option.get("budget", budget)
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
        "genres": sorted(genres),
        "budget": budget,
        "first_day": valid_day(answers.get("premiere")),
        "names": (answers.get("prenoms") or "").strip()[:80] or None,
    }


def valid_day(value: Any) -> str | None:
    """A day as the page sends it (2026-10-09), or None."""
    try:
        return date.fromisoformat(value).isoformat() if isinstance(value, str) and len(value) == 10 else None
    except ValueError:
        return None


def valid_profile(value: Any) -> dict[str, Any] | None:
    """A profile as the page sends it back (its own, computed by /api/profiles or synced from Supabase), or None.

    The profile the couple sends back is not read from the store, so this is the trust boundary: reshape it into
    exactly what `requests_for`/`evening` read, dropping anything unexpected.
    """
    if not isinstance(value, dict):
        return None
    try:
        return {
            "vibes": [v for v in value["vibes"] if v in VIBES][:MAX_VIBES] or ["romantique"],
            "audace": max(0.0, min(1.0, float(value["audace"]))),
            "avoid": [v for v in value.get("avoid") or [] if isinstance(v, str)],
            "prefer": [v for v in value.get("prefer") or [] if isinstance(v, str)],
            "genres": [v for v in value.get("genres") or [] if v in GENRES],
            "budget": max(1.0, min(1000.0, float(value["budget"]))),
            "first_day": valid_day(value.get("first_day")),
            "names": (str(value["names"])[:80] if value.get("names") else None),
        }
    except (KeyError, TypeError, ValueError):
        return None


MAX_VOTES = 500


def valid_votes(value: Any) -> dict[tuple[str, str], int]:
    """The couple's votes as the page sends them ({"source_id:external_id": 1 or -1}), by activity key; anything
    else dropped."""
    if not isinstance(value, dict):
        return {}
    votes = {}
    for name, vote in list(value.items())[:MAX_VOTES]:
        source_id, _, external_id = str(name).partition(":")
        if source_id and external_id and vote in (1, -1) and not isinstance(vote, bool):
            votes[(source_id, external_id)] = vote
    return votes


ENVIE_KEYS = {envie["value"]: envie for envie in ENVIES}
OCCASION_KEYS = {occasion["value"]: occasion for occasion in OCCASIONS}
SQUAD_ENVIE_KEYS = {envie["value"]: envie for envie in SQUAD_ENVIES}
SQUAD_OCCASION_KEYS = {occasion["value"]: occasion for occasion in SQUAD_OCCASIONS}
START_KEYS = {option["value"]: option for option in START_OPTIONS}
END_KEYS = {option["value"]: option for option in END_OPTIONS}


MAX_VIBES = 5


def _late(hour: str) -> str:
    """An hour as the evening sees it: 03:30 comes after 23:30."""
    return f"{int(hour[:2]) + 24}{hour[2:]}" if hour < "12:00" else hour


def evening(
    profile: dict[str, Any], envies: list[str] | None = None, occasion: str | None = None, dinner: bool | None = None,
    start: str | None = None, end: str | None = None, squad: bool = False,
) -> dict[str, Any]:
    """One evening's settings: its wishes and occasion over the profile, which keeps refusals and tastes.

    `dinner`, `start`, `end`: asked each time (/soiree), not kept in the profile; they win over what
    the wishes would otherwise set. Not said (None): inferred from the wishes, or the defaults.
    `squad`: a band's evening (Secret Squad), with its own wishes and occasions.
    """
    envie_keys, occasion_keys = (SQUAD_ENVIE_KEYS, SQUAD_OCCASION_KEYS) if squad else (ENVIE_KEYS, OCCASION_KEYS)
    first = SQUAD_ENVIES[0] if squad else ENVIES[0]
    wishes = [envie_keys[e] for e in dict.fromkeys(envies or []) if e in envie_keys][:MAX_ENVIES] or [first]
    event = occasion_keys.get(occasion or "rien", occasion_keys["rien"])
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
        # What the wishes and the occasion favour besides their vibes: karaoke to sing, a hen party's offers.
        "prefer": sorted(set(profile["prefer"]).union(*(w.get("prefer") or [] for w in wishes), event.get("prefer") or [])),
        "dinner": dinner if dinner is not None else any(w.get("dinner") for w in wishes) or bool(event.get("dinner")),
        "no_dinner": dinner is False,
        "start": START_KEYS[start]["start"] if start in START_KEYS else min((w["start"] for w in wishes if "start" in w), default=DEFAULT_START),
        "end": END_KEYS[end]["end"] if end in END_KEYS else (max(ends, key=_late) if ends else DEFAULT_END),
    }


def requests_for(
    profile: dict[str, Any], days: list[date] | None = None, envies: list[str] | None = None, occasion: str | None = None,
    dinner: bool | None = None, overnight: bool = False, start: str | None = None, end: str | None = None,
    budget: float | None = None, party: int = 2, formule: str = "duo",
) -> list[parcours.Request]:
    """The evenings to plan for a profile and wishes: the days given, its first outing, else the next Friday and Saturday.

    `overnight`: the couple sleeps out, the evening ends in a hotel or a love room. `budget`: this evening's
    budget, in place of the profile's typical one, when the couple adjusts it for this occasion; the whole party's.
    `party`, `formule`: a band of friends' evening (Secret Squad, "squad"), how many they are; a couple's ("duo")."""
    if not days:
        if profile.get("first_day"):
            days = [date.fromisoformat(profile["first_day"])]
        else:
            today = date.today()
            friday = today + timedelta(days=(4 - today.weekday()) % 7)
            days = [friday, friday + timedelta(days=1)]
    night = evening(profile, envies, occasion, dinner, start, end, squad=formule == "squad")
    requests = []
    for day in days:
        begin, finish = parcours.window(day, night["start"], night["end"])
        requests.append(parcours.Request(
            day, budget if budget is not None else profile["budget"], begin, finish, night["vibes"],
            party=party, formule=formule,
            audace=night["audace"], avoid=set(night["avoid"]), prefer=set(night["prefer"]), genres=set(profile.get("genres") or []),
            dinner=night["dinner"],
            no_dinner=night["no_dinner"], overnight=overnight,
        ))
    return requests


def new_id() -> str:
    return secrets.token_urlsafe(6)


# /api/parcours/<page>/routes/<index>[/steps/<position>]: draw a route, or one of its steps, again.
_REDO = re.compile(r"^/api/parcours/(?P<name>[\w-]+)/routes/(?P<route>\d+)(?:/steps/(?P<step>\d+))?$")
# /api/parcours/<page>/routes/<index>/steps/<position>/remove: the couple takes a step out.
_REMOVE = re.compile(r"^/api/parcours/(?P<name>[\w-]+)/routes/(?P<route>\d+)/steps/(?P<step>\d+)/remove$")
# /api/parcours/<page>/routes/<index>/choose: the couple keeps this route, the page's only one from then on.
_CHOOSE = re.compile(r"^/api/parcours/(?P<name>[\w-]+)/routes/(?P<route>\d+)/choose$")
BASE_MINUTES = 15


def make_handler(db: Path | str | None, checks: int, warm: bool = False) -> type[BaseHTTPRequestHandler]:
    parcours.DB = db
    # One composition at a time: it checks booking engines and writes the page.
    composing = threading.Lock()
    # The activities take seconds to load: loaded when the server starts, then again in the background
    # when a quarter of an hour old, the evening being composed meanwhile with the previous ones.
    loaded: dict[str, Any] = {}
    loading = threading.Lock()

    def reload() -> None:
        with open_store(db) as store:
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
        with open_store(db) as store:
            base(store)

    if warm:
        threading.Thread(target=warm_up, daemon=True).start()

    # The moderation page and its API (/admin, /api/activities, /api/meta…) come with it.
    class Handler(admin.make_handler(db)):
        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/api/quiz":
                vibes = {key: v["label"] for key, v in VIBES.items()}
                self._send_json(HTTPStatus.OK, {"questions": QUESTIONS, "vibes": vibes})
            elif path == "/api/soiree":
                # ?formule=squad: a band's evening (Secret Squad), its wishes, occasions and budgets per person.
                if parse_qs(urlsplit(self.path).query).get("formule") == ["squad"]:
                    return self._send_json(HTTPStatus.OK, {
                        "formule": "squad", "envies": SQUAD_ENVIES, "moods": SQUAD_MOODS, "occasions": SQUAD_OCCASIONS,
                        "max": MAX_ENVIES, "starts": START_OPTIONS, "ends": END_OPTIONS, "budgets": SQUAD_BUDGET_OPTIONS,
                        "personnes": SQUAD_PERSONNES, "eviter": SQUAD_EVITER,
                        "vibes": {key: SQUAD_VIBE_LABELS.get(key, v["label"]) for key, v in VIBES.items()},
                    })
                self._send_json(HTTPStatus.OK, {
                    "formule": "duo", "envies": ENVIES, "moods": MOODS, "occasions": OCCASIONS, "max": MAX_ENVIES,
                    "starts": START_OPTIONS, "ends": END_OPTIONS, "budgets": BUDGET_OPTIONS,
                })
            elif re.match(r"^/api/parcours/[\w-]+$", path):
                # Polled while `naming` (Claude's titles still coming), and to reload a redrawn evening.
                state = parcours.load(path.rsplit("/", 1)[1])
                if state is None:
                    return self._send_json(HTTPStatus.NOT_FOUND, {"error": "introuvable"})
                self._send_json(HTTPStatus.OK, parcours.soiree_json(path.rsplit("/", 1)[1], state))
            elif re.match(r"^/images/\w+\.\w+$", path) and (image := images.DIRECTORY / path.removeprefix("/images/")).exists():
                self._send(HTTPStatus.OK, image.read_bytes(), images.MEDIA_TYPES.get(image.suffix, "application/octet-stream"))
            elif page := web_file(path):
                kind = TYPES.guess_type(page.name)[0] or "application/octet-stream"
                self._send(HTTPStatus.OK, page.read_bytes(), kind + ("; charset=utf-8" if kind.startswith("text/") else ""))
            elif path == "/" and not WEB.exists():
                self._send(HTTPStatus.SERVICE_UNAVAILABLE, "Site pas encore construit : npm run build:web dans app/".encode(), "text/plain; charset=utf-8")
            else:
                super().do_GET()

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            if path.startswith("/api/activities/"):
                super().do_POST()
                # A fiche rejected in moderation is never proposed again: the next evening reloads the activities.
                with loading:
                    loaded.pop("base", None)
                return
            # Requiring JSON forces a CORS preflight, so other sites cannot post here.
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                return self._send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "JSON attendu"})
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            except ValueError:
                return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "JSON invalide"})
            if path == "/api/profiles":
                # The couple keeps its profile client-side (localStorage, and couple_profiles once signed
                # in) and sends it back with each evening; every profile drawn is also recorded here.
                answers = body.get("answers") if isinstance(body.get("answers"), dict) else {}
                profile = profile_from(answers)
                with open_store(db) as store:
                    store.save_profile(new_id(), answers, profile)
                return self._send_json(HTTPStatus.OK, {"profile": profile})
            if path == "/api/soirees":
                return self._compose(body)
            if path == "/api/images/broken":
                # A page could not show a step's image, even on a second try: another one, or null (its own picture).
                key, url = str(body.get("id") or "").partition(":")[::2], body.get("url")
                if not all(key) or not isinstance(url, str):
                    return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "étape ou image manquante"})
                with open_store(db) as store:
                    found = base(store)
                return self._send_json(HTTPStatus.OK, {"image_url": parcours.broken_image(found, key, url)})
            if remove := _REMOVE.match(path):
                if error := parcours.remove(remove["name"], int(remove["route"]), int(remove["step"])):
                    return self._send_json(HTTPStatus.CONFLICT, {"error": error})
                return self._send_json(HTTPStatus.OK, parcours.soiree_json(remove["name"], parcours.load(remove["name"])))
            if choose := _CHOOSE.match(path):
                with open_store(db) as store:
                    if error := parcours.choose(choose["name"], int(choose["route"]), store):
                        return self._send_json(HTTPStatus.CONFLICT, {"error": error})
                    return self._send_json(HTTPStatus.OK, parcours.soiree_json(choose["name"], parcours.load(choose["name"], store)))
            if redo := _REDO.match(path):
                return self._redo(redo["name"], int(redo["route"]), None if redo["step"] is None else int(redo["step"]))
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "introuvable"})

        def _compose(self, body: dict[str, Any]) -> None:
            """An evening's routes: its wishes, occasion and day, with the profile given or default settings.

            `formule` "squad": a band's evening (Secret Squad), for `personnes`; its budget is per person, and nothing
            but its order counts (`eviter`, what it never wants): no profile, no votes."""
            squad = body.get("formule") == "squad"
            party = body.get("personnes") if squad else 2
            if squad and not (isinstance(party, int) and not isinstance(party, bool) and SQUAD_PERSONNES["min"] <= party <= SQUAD_PERSONNES["max"]):
                return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "nombre de personnes invalide"})
            envie_keys, occasion_keys = (SQUAD_ENVIE_KEYS, SQUAD_OCCASION_KEYS) if squad else (ENVIE_KEYS, OCCASION_KEYS)
            asked = body.get("envies") if isinstance(body.get("envies"), list) else []
            envies = [e for e in dict.fromkeys(e for e in asked if isinstance(e, str)) if e in envie_keys][:MAX_ENVIES]
            if not envies:
                return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "au moins une envie"})
            if not isinstance(body.get("diner"), bool):
                return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "dîner ou pas ?"})
            occasion = body.get("occasion") if body.get("occasion") in occasion_keys else None
            start = body.get("start") if body.get("start") in START_KEYS else None
            end = body.get("end") if body.get("end") in END_KEYS else None
            budget = body.get("budget")
            if budget is not None and not (isinstance(budget, (int, float)) and not isinstance(budget, bool) and 0 < budget <= 1000):
                return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "budget invalide"})
            if squad:
                budget = (budget or SQUAD_BUDGET) * party  # per person, for the band
            day = valid_day(body.get("day"))
            days = [date.fromisoformat(day)] if day else None
            if squad:
                eviter = body.get("eviter") if isinstance(body.get("eviter"), list) else []
                profile = squad_profile([e for e in eviter[:len(SQUAD_EVITER)] if isinstance(e, str)])
            elif body.get("profile") is None:
                profile = profile_from({})
            elif (profile := valid_profile(body.get("profile"))) is None:
                return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "profil invalide"})
            # The evenings the couple chose (its history, by their pages): their activities are never proposed again.
            chosen = body.get("done") if isinstance(body.get("done"), list) else []
            chosen = [name for name in chosen[:200] if isinstance(name, str)]
            # Their votes on the steps of evenings before: the kinds liked come first, those voted out never.
            votes = {} if squad else valid_votes(body.get("votes"))
            with open_store(db) as store:
                found = base(store)
                # Never again: the activities of the evenings chosen, and those voted down.
                done = store.chosen_activities(chosen) | {key for key, vote in votes.items() if vote < 0}
                tastes = parcours.tastes_from(found, votes)
                overnight = body.get("decoucher") is True and not squad  # a band goes home
                name = f"soiree-{new_id()}-{f'squad{party}-' if squad else ''}{'-'.join(envies)}-{'diner' if body['diner'] else 'sans-diner'}"
                name += "-nuit" if overnight else ""
                with composing:
                    requests = requests_for(
                        profile, days, envies, occasion, body["diner"], overnight, start, end, budget,
                        party=party, formule="squad" if squad else "duo",
                    )
                    for request in requests:
                        request.done = done
                        request.tastes = tastes
                    _, name = parcours.generate(
                        store, requests,
                        count=3, checks=checks, name=name, base=found, name_later=True,
                    )
                    state = parcours.load(name, store)
            self._send_json(HTTPStatus.OK, parcours.soiree_json(name, state))

        def _redo(self, name: str, index: int, position: int | None) -> None:
            """Another route in place of route `index`, or another activity at its step `position`."""
            with open_store(db) as store, composing:
                error = parcours.regenerate(store, base(store), name, index, position, checks=min(checks, 10))
                state = parcours.load(name, store)
            if error:
                return self._send_json(HTTPStatus.CONFLICT, {"error": error})
            self._send_json(HTTPStatus.OK, parcours.soiree_json(name, state))

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Questionnaire client : profil du couple, puis ses soirées")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--host", default="127.0.0.1", help="0.0.0.0 pour tester depuis un téléphone sur le même Wi-Fi")
    parser.add_argument("--db", help="base SQLite ou URL postgresql:// (défaut : SUPABASE_DB_URL, sinon data/surprise.db)")
    parser.add_argument("--checks", type=int, default=30, help="vérifications de disponibilité en direct par soirée composée")
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    # A Windows console cannot show every character (✓, ✗): replace them rather than fail.
    sys.stdout.reconfigure(errors="replace")
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.db, args.checks, warm=True))
    url = f"http://127.0.0.1:{args.port}"
    print(f"Site (l'app) : {url}  ·  modération : {url}/admin")
    if args.host == "0.0.0.0":
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            lan_ip = s.getsockname()[0]
        print(f"Sur le même Wi-Fi (téléphone…) : http://{lan_ip}:{args.port}")
    if not args.no_open:
        webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__":
    main()
