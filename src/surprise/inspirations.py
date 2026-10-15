"""The couple's content fed beside the collection: ideas harvested, re-imagined, then published by the moderation.

    uv run --env-file .env python -m surprise.inspirations aspirer --limit 50    # the pages read again after 30 days
    uv run --env-file .env python -m surprise.inspirations reimaginer [--claude] # our version of each new idea
    then /admin/contenus: retouch a version, publish it or set it aside; eight quiz questions kept make a series.

The public pages of couple questions, quizzes and tests (Ozer, Quiz Couple, Psychologies, Psychologue.net, Elle,
Tostadora, Bridebook, Mariages.net) give ideas, each kept with its genre (a question of the day, a quiz question, a
défi) and its palier guessed by the rules. The sources' words never reach the app: an idea is shown to the moderation
only, and a version is published only once far enough from it (CLOSE). Our version is drafted by the rules by default
(the app's register, a quiz question turned into « Mon plat préféré », the partner become « moi »), by Claude with
--claude (ANTHROPIC_API_KEY), or written in the moderation. Published at the end of the journey (the next id), the
duos' progress stays where it is.
"""

import argparse
import hashlib
import json
import os
import re
import time as clock
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Callable

import httpx

from surprise.collectors.facts import BROWSER_HEADERS, text
from surprise.local_store import LocalStore, open_store

# The pages, by source: those the couple's content was first written from (docs/complicite.md, Sources).
SOURCES: dict[str, tuple[str, list[str]]] = {
    "ozer": ("Ozer", ["https://ozerlove.com/quiz-couple"]),
    "quiz_couple": ("Quiz Couple", ["https://quiz-couple.com/blog/questions-pour-mieux-se-connaitre-en-couple/"]),
    "psychologies": ("Psychologies", ["https://www.psychologies.com/couple/tests-couple"]),
    "psychologue_net": ("Psychologue.net", ["https://www.psychologue.net/articles/21-questions-pour-savoir-a-quel-point-vous-connaissez-votre-partenaire"]),
    "elle": ("Elle", ["https://www.elle.fr/Love-Sexe/Tests-et-quiz/Relations/Connaissez-vous-bien-votre-partenaire"]),
    "tostadora": ("Tostadora", ["https://www.tostadora.fr/blog/couple/question-couple/"]),
    "bridebook": ("Bridebook", ["https://bridebook.com/fr/article/testez-votre-couple-le-jeu-des-20-questions-piege-et-hilarantes"]),
    "mariages_net": ("Mariages.net", ["https://www.mariages.net/articles/les-18-questions-a-poser-a-votre-partenaire-pour-mieux-le-connaitre--c10998"]),
}
# A page read less than this long ago is not read again: such lists change slowly.
PAGE_DAYS = 30
DELAY_SECONDS = 1.0
# Above this likeness to the source's words (0 to 1, letters only), a version is the source's, not ours.
CLOSE = 0.75
GENRES = ("question", "quiz", "defi", "carte")
THEMES = ("absurde", "tu préfères", "souvenirs", "enfance", "goûts", "quotidien", "rêves", "valeurs", "nous", "désir")
DEFI_GENRES = ("geste", "rituel", "sortie", "jeu")
DEFAULT_MODEL = "claude-opus-5-5"

_BLOCK = re.compile(r"<(li|h[2-4]|p|strong|b|td)\b[^>]*>(.*?)</\1>", re.DOTALL | re.IGNORECASE)
_HIDDEN = re.compile(r"<(script|style|nav|footer|header|aside|form|noscript)\b.*?</\1>", re.DOTALL | re.IGNORECASE)
_NUMBERING = re.compile(r"^[\W_]*(?:question\s*)?(?:n°\s*)?\d{1,3}\s*[.)/:—–-]?\s*|^[«\"“\s]+|[»\"”\s]+$", re.IGNORECASE)
# A défi says what to do, to both: "Écrivez-vous une lettre…", "Organisez un pique-nique…".
_DEFI = re.compile(
    r"^(?:écri(?:vez|s)|offre[sz]?|fai(?:tes|s)|organise[sz]?|prépare[sz]?|cuisine[sz]?|envoie[sz]?|glisse[sz]?|planifie[sz]?|"
    r"choisi(?:ssez|s)|raconte[sz]?|danse[sz]?|parte[sz]|teste[sz]?|essaye[sz]?|apprene[sz]|regarde[sz]?|recréez|refaites)\b",
    re.IGNORECASE,
)
# What a page says of itself, never an idea.
_NOISE = re.compile(r"cookie|newsletter|abonne|partag|commentaire|connexion|inscri|mot de passe|téléchar|quiz couple ?\?$|lire aussi|notre test|ce test|le test|testez votre|faites le test", re.IGNORECASE)
# A quiz question: what the other likes or is, to guess ("Quel est son plat préféré ?", "… de votre partenaire").
_QUIZ = re.compile(
    r"^(?:quel(?:le)?s?|combien|où|comment)\b.*\b(?:son|sa|ses|préférée?s?|favorite?s?)\b|\b(?:préférée?s?|favorite?s?)\b.*(?:de (?:votre|ton|ta) partenaire|de l'autre)\b",
    re.IGNORECASE,
)
_QUIZ_OPENING = re.compile(r"^quel(?:le)?s?\s+(?:est|était|sont|étaient|serait|seraient)\s+", re.IGNORECASE)
_QUIZ_PARTNER = re.compile(r"\s+(?:de|chez)\s+(?:votre|ton|ta|sa|son)\s+(?:partenaire|moitié|conjointe?|chérie?|amoureuse|amoureux)|\s+de l'autre", re.IGNORECASE)
_QUIZ_MINE = {"son": "mon", "sa": "ma", "ses": "mes", "votre": "mon", "vos": "mes", "ton": "mon", "ta": "ma", "tes": "mes"}
# The quotes a page wraps its questions in: "Côté communication : « Quand te sens-tu… ?".
_QUOTED = re.compile(r"^.*«\s*|^[»,\s]+")

_PALIERS = [
    (4, re.compile(r"peur|regret|blessure|pardonn|secret|sexu|intim|vulnérab|honte|pleur|mort|jaloux|jalous|trahi|manque", re.IGNORECASE)),
    (3, re.compile(r"disput|conflit|confiance|avenir|enfants|famille|besoin|amour|couple|relation|engag|valeur", re.IGNORECASE)),
    (2, re.compile(r"souvenir|enfance|rêve|premi(?:er|ère)|fier|fière|admir|apprécie", re.IGNORECASE)),
]
_THEMES = [
    ("tu préfères", re.compile(r"\bpréfér\w*\b.+\bou\b|\bplutôt\b.+\bou\b", re.IGNORECASE)),
    ("désir", re.compile(r"désir|sensuel|sexu|séduction|baiser", re.IGNORECASE)),
    ("enfance", re.compile(r"enfan|petit(?:e)? (?:fille|garçon)|école|récré", re.IGNORECASE)),
    ("souvenirs", re.compile(r"souvenir|premi(?:er|ère)|rencontr", re.IGNORECASE)),
    ("rêves", re.compile(r"rêve|avenir|futur|dans \d+ ans|un jour", re.IGNORECASE)),
    ("absurde", re.compile(r"\bsi (?:tu|vous) (?:étai|pouvai|deven)|super-?pouvoir|zombie|île déserte|animal", re.IGNORECASE)),
    ("goûts", re.compile(r"plat|cuisine|film|musique|chanson|livre|couleur|série", re.IGNORECASE)),
    ("valeurs", re.compile(r"valeur|important|justice|argent|réussi", re.IGNORECASE)),
    ("quotidien", re.compile(r"matin|soir|journée|maison|ménage|habitude", re.IGNORECASE)),
]


def fingerprint(words: str) -> str:
    """The same idea met again (case, accents, punctuation aside): the same id."""
    return hashlib.sha1(_letters(words).encode()).hexdigest()[:16]


def _letters(words: str) -> str:
    plain = unicodedata.normalize("NFD", words.lower().replace("’", "'"))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", "".join(c for c in plain if not unicodedata.combining(c))).split())


def too_close(source: str, version: str) -> bool:
    return SequenceMatcher(None, _letters(source), _letters(version)).ratio() > CLOSE


def extract(page: str) -> list[str]:
    """The ideas of a page, in its order: its questions, and what it gives to do."""
    body = re.search(r"<article\b.*?</article>", page, re.DOTALL) or re.search(r"<main\b.*?</main>", page, re.DOTALL)
    body = _HIDDEN.sub(" ", body.group(0) if body and len(body.group(0)) > 2000 else page)
    ideas, seen = [], set()
    for _, fragment in _BLOCK.findall(body):
        # A paragraph of several questions: each one.
        for part in re.split(r"(?<=[.!?…])\s+", text(fragment)):
            idea = _NUMBERING.sub("", _QUOTED.sub("", part)).strip()
            if not 15 <= len(idea) <= 220 or _NOISE.search(idea) or not (idea.endswith("?") or _DEFI.match(idea)):
                continue
            if (key := fingerprint(idea)) not in seen:
                seen.add(key)
                ideas.append(idea)
    return ideas


def classify(idea: str) -> tuple[str, int]:
    """Its genre (question, quiz, défi) and palier (1 the lightest, 4 the most intimate), by the rules."""
    genre = "defi" if _DEFI.match(idea) and not idea.endswith("?") else "quiz" if _QUIZ.search(idea) else "question"
    palier = next((level for level, words in _PALIERS if words.search(idea)), 1)
    return genre, palier


def theme_of(idea: str) -> str:
    return next((theme for theme, words in _THEMES if words.search(idea)), "nous")


# The app speaks to the other with « tu »: the sources' « vous » become it, the partner spoken of becomes « moi ».
_IRREGULAR = {
    "avez": "as", "êtes": "es", "pouvez": "peux", "voulez": "veux", "faites": "fais", "dites": "dis", "allez": "vas",
    "savez": "sais", "prenez": "prends", "voyez": "vois", "croyez": "crois", "venez": "viens", "devez": "dois",
    "sentez": "sens", "mettez": "mets", "vivez": "vis", "connaissez": "connais", "souvenez": "souviens", "choisissez": "choisis",
}
_PARTNER = r"(?:votre|ton|ta)\s+(?:partenaire|moitié|conjointe?|chérie?|amoureuse|amoureux)|l'autre"


def _second_person(verb: str) -> str:
    low = verb.lower()
    if low in _IRREGULAR:
        return _IRREGULAR[low]
    if low.endswith("iez"):  # aimeriez → aimerais, voudriez → voudrais
        return verb[:-3] + "ais"
    if low.endswith("ez"):  # aimez → aimes, préférez → préfères
        return re.sub(r"é([^aeiouyéèê]+)$", r"è\1", verb[:-2]) + "es"
    return verb


def _same_case(model: str, word: str) -> str:
    return word[:1].upper() + word[1:] if model[:1].isupper() else word


def tutoyer(words: str) -> str:
    words = words.replace("’", "'")
    # A noun, not a verb: kept apart while the rest changes.
    words = re.sub(r"\brendez-vous\b", "rendez_vous", words, flags=re.IGNORECASE)
    words = re.sub(rf"\b(chez|avec|pour|de|à|sans|envers|sur|contre)\s+{_PARTNER}\b", r"\1 moi", words, flags=re.IGNORECASE)
    # « Vous sentez-vous » → « Te sens-tu », « Avez-vous » → « As-tu ».
    words = re.sub(r"\b(?:([Vv]ous) )?(\w+)-vous\b", lambda m: (
        _same_case(m.group(1), _te(_second_person(m.group(2)))) + _second_person(m.group(2)).lower() + "-tu" if m.group(1)
        else _same_case(m.group(2), _second_person(m.group(2))) + "-tu"
    ), words)
    # « Vous vous souvenez » → « Tu te souviens ».
    words = re.sub(r"\b([Vv]ous) vous (\w+)", lambda m: f"{_same_case(m.group(1), 'tu')} {_te(m.group(2))}{_second_person(m.group(2))}", words)
    words = re.sub(r"\b(chez|avec|pour|de|à|sans|selon|envers|sur|contre|que|qu'à)\s+vous\b(?!\s+(?:\w+(?:ez|iez)|êtes|faites|dites)\b)", r"\1 toi", words)
    words = re.sub(r"\b([Vv]ous) (\w+(?:ez|iez)|êtes|faites|dites)\b", lambda m: f"{_same_case(m.group(1), 'tu')} {_second_person(m.group(2))}", words)
    words = re.sub(r"\b([Vv]ous) (\w+)", lambda m: _same_case(m.group(1), _te(m.group(2))) + m.group(2), words)
    words = re.sub(r"\bVotre\b", "Ton", re.sub(r"\bvotre\b", "ton", words))
    words = re.sub(r"\bVos\b", "Tes", re.sub(r"\bvos\b", "tes", words))
    return words.replace("rendez_vous", "rendez-vous").replace("Rendez_vous", "Rendez-vous")


def _te(following: str) -> str:
    """« te » before a verb, « t' » before a vowel."""
    return "t'" if following[:1].lower() in "aeiouyéèêàh" else "te "


def quiz_stem(words: str) -> str:
    """A question on the other as the quiz asks it, in the first person: « Quel est son plat préféré ? » → « Mon plat préféré »."""
    stem = _QUIZ_PARTNER.sub("", _QUIZ_OPENING.sub("", words.replace("’", "'"))).rstrip(" ?")
    stem = re.sub(r"\b(son|sa|ses|votre|vos|ton|ta|tes)\b",lambda m: _same_case(m.group(1), _QUIZ_MINE[m.group(1).lower()]), stem, flags=re.IGNORECASE)
    # « La couleur préférée » → « Ma couleur préférée ».
    if not re.search(r"\b(?:mon|ma|mes)\b", stem, re.IGNORECASE):
        stem = re.sub(r"^(?:(le|la|les)\s+|(l')\s*)", lambda m: {"le": "mon ", "la": "ma ", "les": "mes ", "l'": "mon "}[(m.group(1) or m.group(2)).lower()], stem, flags=re.IGNORECASE)
    return stem[:1].upper() + stem[1:]


def by_rules(idea: dict[str, Any]) -> dict[str, Any]:
    """A first version of an idea, in the shape of its genre, drawn by the rules: to retouch before it is published."""
    words, genre = idea["texte"], idea["genre"]
    if genre == "quiz":
        return {"question": quiz_stem(words), "choix": ["", "", "", ""]}
    if genre == "defi":
        return {"titre": "", "texte": words, "genre": "geste"}
    if genre == "carte":
        return {"texte": tutoyer(words), "genre": "conversation", "profondeur": min(3, idea["palier"])}
    return {"texte": tutoyer(words), "theme": theme_of(words), "palier": idea["palier"]}


_SYSTEM = """Tu écris les contenus d'une app de sorties en couple à Paris : des questions du jour pour deux, un quiz où
chacun répond pour soi et devine l'autre, des défis de la semaine, des cartes à piocher pendant la soirée. Ton ton :
drôle, tendre, inattendu, jamais bateau ni niais. Tu reçois une idée trouvée sur un site : tu n'en reprends pas les
mots, tu en inventes une version neuve, avec un angle à toi (un scénario, un détail concret, une image). Les questions
et les cartes tutoient l'autre (« tu », « moi »). Les questions du quiz sont à la première personne, sans point
d'interrogation (« Mon dimanche parfait »), avec quatre réponses courtes et parlantes. Les défis vouvoient le duo
(« Glissez un petit mot… »). Pas de formes genrées quand on peut l'éviter. Réponds par un seul objet JSON, rien d'autre."""
_SHAPES = {
    "question": '{"texte": "… ?", "theme": "un de : ' + ", ".join(THEMES) + '", "palier": 1 à 4}',
    "quiz": '{"question": "Mon …", "choix": ["…", "…", "…", "…"]}',
    "defi": '{"titre": "2 à 5 mots", "texte": "une ou deux phrases", "genre": "un de : ' + ", ".join(DEFI_GENRES) + '"}',
    "carte": '{"texte": "…", "genre": "conversation ou defi", "profondeur": 1 à 3}',
}


def by_claude(client: Any, model: str, idea: dict[str, Any]) -> dict[str, Any] | None:
    """A version written by Claude; None when it cannot be had (the rules' then)."""
    prompt = (f"Idée ({idea['genre']}, palier {idea['palier']} sur 4, 1 le plus léger) : {idea['texte']}\n"
              f"Réponds au format : {_SHAPES[idea['genre']]}")
    try:
        response = client.messages.create(model=model, max_tokens=1000, system=_SYSTEM, messages=[{"role": "user", "content": prompt}])
    except Exception as error:
        import anthropic  # for its errors only

        if isinstance(error, anthropic.APIConnectionError) or (isinstance(error, anthropic.APIStatusError) and error.status_code not in (400, 404)):
            return None
        raise
    answer = "".join(block.text for block in response.content if block.type == "text")
    found = re.search(r"\{.*\}", answer, re.DOTALL)
    try:
        version = json.loads(found.group(0)) if found else None
        if version is not None:
            check(idea["genre"], version)
            if too_close(idea["texte"], _words_of(idea["genre"], version)):
                return None
    except (ValueError, TypeError):
        return None
    return version


def _words_of(genre: str, version: dict[str, Any]) -> str:
    return version["question"] if genre == "quiz" else version["texte"]


def check(genre: str, version: dict[str, Any]) -> None:
    """A version the app can show, else a ValueError saying what is missing."""
    def need(ok: bool, message: str) -> None:
        if not ok:
            raise ValueError(message)

    need(genre in GENRES, f"Genre attendu : {', '.join(GENRES)}.")
    if genre == "question":
        texte = (version.get("texte") or "").strip()
        need(15 <= len(texte) <= 220 and texte.endswith("?"), "Une question de 15 à 220 caractères, finie par « ? ».")
        need(version.get("theme") in THEMES, f"Un thème parmi : {', '.join(THEMES)}.")
        need(version.get("palier") in (1, 2, 3, 4), "Un palier de 1 à 4.")
    elif genre == "quiz":
        need(3 <= len((version.get("question") or "").strip()) <= 120, "Une question de quiz de 3 à 120 caractères.")
        choix = [c.strip() for c in version.get("choix") or [] if isinstance(c, str)]
        need(len(choix) == 4 and all(choix) and len(set(choix)) == 4, "Quatre réponses, toutes différentes.")
    elif genre == "defi":
        need(2 <= len((version.get("titre") or "").strip()) <= 60, "Un titre de défi.")
        need(20 <= len((version.get("texte") or "").strip()) <= 300, "Le défi en une ou deux phrases (20 à 300 caractères).")
        need(version.get("genre") in DEFI_GENRES, f"Un genre de défi parmi : {', '.join(DEFI_GENRES)}.")
    else:
        need(15 <= len((version.get("texte") or "").strip()) <= 220, "Une carte de 15 à 220 caractères.")
        need(version.get("genre") in ("conversation", "defi"), "Une carte de conversation ou de défi.")
        need(version.get("profondeur") in (1, 2, 3), "Une profondeur de 1 à 3.")


def aspirer(store: LocalStore, http: httpx.Client, limit: int = 50, refresh: bool = False,
            sources: list[str] | None = None, delay: float = DELAY_SECONDS) -> Counter[str]:
    """The sources' pages not read for PAGE_DAYS (all with `refresh`), at most `limit` ideas each: the new ones by source."""
    fresh = set() if refresh else store.inspiration_pages(PAGE_DAYS)
    added: Counter[str] = Counter()
    for source_id, (_, urls) in SOURCES.items():
        if sources and source_id not in sources:
            continue
        for url in urls:
            if url in fresh:
                continue
            clock.sleep(delay)
            try:
                response = http.get(url)
                response.raise_for_status()
            except httpx.HTTPError as error:
                print(f"{source_id} : {url} illisible ({error})")
                continue
            ideas = []
            for words in extract(response.text)[:limit]:
                genre, palier = classify(words)
                ideas.append({"id": fingerprint(words), "texte": words, "genre": genre, "palier": palier})
            added[source_id] += store.save_inspirations(source_id, url, ideas)
    return added


def reimaginer(store: LocalStore, writer: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
               by: str = "regles", limit: int | None = None) -> int:
    """Our version of each new idea: the writer's (Claude) when it gives one, else the rules'. The count drafted."""
    ideas = store.inspirations("nouvelle")[:limit]
    for idea in ideas:
        version = writer(idea) if writer else None
        store.decide_inspiration(idea["id"], "proposee", version or by_rules(idea), by if version else "regles")
    return len(ideas)


def _idea(store: LocalStore, idea_id: str) -> dict[str, Any]:
    found = next((idea for idea in store.inspirations() if idea["id"] == idea_id), None)
    if found is None:
        raise LookupError("Inspiration inconnue.")
    return found


def publier(store: LocalStore, idea_id: str, genre: str, version: dict[str, Any]) -> str:
    """Our version of an idea, at the end of its journey in the app; a quiz question kept for its series of eight.
    Where it went ("questions_du_jour:109"), or "gardee"."""
    idea = _idea(store, idea_id)
    if idea["statut"] == "publiee":
        raise ValueError("Déjà publiée.")
    check(genre, version)
    if too_close(idea["texte"], _words_of(genre, version)):
        raise ValueError("Trop proche des mots de la source : à réécrire avec les nôtres.")
    if genre == "quiz":
        store.decide_inspiration(idea_id, "gardee", version, "moderation")
        return "gardee"
    if genre == "question":
        table, row = "questions_du_jour", {"profondeur": version["palier"], "theme": version["theme"], "texte": version["texte"].strip()}
    elif genre == "defi":
        table, row = "defis", {"genre": version["genre"], "titre": version["titre"].strip(), "texte": version["texte"].strip(), "envie": None}
    else:
        table, row = "cartes_du_soir", {"formule": "duo", "genre": version["genre"], "role": None, "profondeur": version["profondeur"],
                                        "texte": version["texte"].strip()}
    where = f"{table}:{store.publish_content(table, row)}"
    store.decide_inspiration(idea_id, "publiee", version, "moderation", where)
    return where


def publier_serie(store: LocalStore, titre: str, accroche: str, idea_ids: list[str]) -> str:
    """Eight quiz questions kept, in the given order, as a new series at the end of the quiz's journey."""
    kept = {idea["id"]: idea for idea in store.inspirations("gardee") if idea["genre"] == "quiz"}
    if len(idea_ids) != 8 or len(set(idea_ids)) != 8 or not all(i in kept for i in idea_ids):
        raise ValueError("Une série, c'est huit questions de quiz gardées, chacune une fois.")
    if not (2 <= len(titre.strip()) <= 40 and 10 <= len(accroche.strip()) <= 120):
        raise ValueError("Un titre (2 à 40 caractères) et une accroche (10 à 120).")
    where = f"quiz_series:{store.publish_series(titre.strip(), accroche.strip(), [kept[i]['proposition'] for i in idea_ids])}"
    for idea_id in idea_ids:
        store.decide_inspiration(idea_id, "publiee", publiee=where)
    return where


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    steps = parser.add_subparsers(dest="step", required=True)
    harvest = steps.add_parser("aspirer", help="lire les pages des sources (pas celles lues depuis moins de 30 jours)")
    harvest.add_argument("--limit", type=int, required=True, help="idées gardées au plus par page (50 : jamais sans limite)")
    harvest.add_argument("--refresh", action="store_true", help="relire aussi les pages encore fraîches")
    harvest.add_argument("--source", action="append", choices=list(SOURCES), help="cette source seulement (répétable)")
    draft = steps.add_parser("reimaginer", help="notre version de chaque idée nouvelle")
    draft.add_argument("--claude", action="store_true", help="rédigée par Claude (ANTHROPIC_API_KEY) plutôt que par les règles")
    draft.add_argument("--limit", type=int)
    args = parser.parse_args()

    with open_store() as store:
        if args.step == "aspirer":
            with httpx.Client(timeout=20, follow_redirects=True, headers=BROWSER_HEADERS) as http:
                added = aspirer(store, http, args.limit, args.refresh, args.source)
            for source_id, (name, _) in SOURCES.items():
                if not args.source or source_id in args.source:
                    print(f"{name} : {added[source_id]} idées nouvelles")
            return
        writer, by = None, "regles"
        # Only an explicit project key: never other credentials found in the environment.
        if args.claude:
            import anthropic

            model = os.environ.get("SURPRISE_LLM_MODEL", DEFAULT_MODEL)
            client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            writer, by = (lambda idea: by_claude(client, model, idea)), model
        print(f"{reimaginer(store, writer, by, args.limit)} idées réimaginées, à retoucher et publier sur /admin/contenus")


if __name__ == "__main__":
    main()
