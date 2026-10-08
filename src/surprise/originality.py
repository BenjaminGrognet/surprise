"""Originality: how unusual an activity is, from 0 (seen everywhere) to 100 (a story to tell).

The score adds up explainable signals, each with its reason, so it can be
tuned like the tags:
- what the outing is, how far from an ordinary evening (a restaurant, a film, a
  concert: nothing): an escape game, a karaoke, a workshop are not done every
  week, a dinner in the dark hardly ever. From its tags (title and venue) and
  from what its texts say an evening there holds (karaoke, blind tests,
  performers, an immersive set), as a bar's name rarely tells; "lieu insolite"
  category;
- how rare it is in the base: an activity whose kind (its rarest tag) is rare
  here is more original than the hundredth stand-up;
- what its texts say: keywords "insolite", "secret", "immersif", "éphémère"…;
- who picked it: curation media and couple blogs choose off the beaten track;
- what makes it common: tourist classics, big venues, chains, generic tours.

Computed on read, like the tags, so the rules change without collecting again.

    uv run python -m surprise.originality     # distribution and the most original activities
"""

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from surprise.keywords import extract, texts
from surprise.patterns import matcher
from surprise.tags import describe

# How far from an ordinary evening each kind of outing is, by its tags (a restaurant, a film, a concert: 0).
_NATURE = {
    "dans_le_noir": 32, "flottaison": 32, "defouloir": 30, "murder_party": 30, "escape_game": 28, "immersif": 28,
    "souterrain": 28, "cache": 26, "hauteur": 26, "karaoke": 24, "jeu_de_piste": 24, "drag": 24, "magie": 22,
    "cirque": 22, "cabaret": 22, "coquin": 22, "shooting": 22, "artisanat": 22, "ceramique": 22, "parfum_bougie": 22,
    "jeu_video": 20, "quiz": 18, "jeu_actif": 18, "mixologie": 18, "cuisine": 18, "peinture_dessin": 18, "floral": 18,
    "mini_golf": 15, "jeux_de_societe": 15, "sur_l_eau": 14, "chandelles": 14, "vin": 12, "comedie_musicale": 10,
    "danse": 10, "vue": 10, "massage": 10, "spa": 10, "degustation": 10, "frisson": 10,
}
# A workshop's tags, which a restaurant or a bar has in its name ("La Cuisine de…", "Gin Bar"): not one.
_WORKSHOP = {"cuisine", "mixologie", "vin", "peinture_dessin", "floral"}
# What an evening there holds, said in its texts only (a bar's name rarely tells): label, points, pattern. A label
# that is a tag's ("karaoke") is not counted twice when the title already says it.
# Every pattern here reads lowercased text, its own words in lowercase: re.IGNORECASE costs three times as much on the
# long texts of thirty thousand activities, each time the server loads them.
_NATURE_PATTERNS = [
    ("karaoke", 24, re.compile(r"karaok")),
    ("quiz", 18, re.compile(r"blind[- ]tests?|\bquiz")),
    ("performeurs, show", 20, re.compile(r"performeu|cracheurs? de feu|effeuill|burlesque|drag queens?|acrobat|show (?:de|live)")),
    ("immersif", 20, re.compile(r"décors? immersif|univers immersif|immersion totale|décors? de cinéma")),
    ("soirée à thème", 20, re.compile(
        r"halloween|bal masqué|soirée (?:costumée|déguisée|à thème)|déguis|entièrement décoré|décor(?:é|ations?) (?:d'halloween|pour l'occasion)",
    )),
]
# Told by their leading words first (surprise.patterns).
_NATURE_TEXTS = [(label, points, matcher(pattern)) for label, points, pattern in _NATURE_PATTERNS]
# A setting out of the ordinary, said in the title or the venue's name (a text's "near Château-Rouge" is not one).
_SETTING = re.compile(r"ch[âa]teaux?(?![- ](?:rouge|d'eau|landon)| de cartes)|manoir|abbaye|hôtel particulier")
_OFFBEAT_WORDS = {
    "insolite": 8, "secret": 8, "mystérieux": 5, "immersif": 5, "interactif": 4, "éphémère": 5,
    "cave voûtée": 5, "dans le noir": 6, "aux chandelles": 4, "rétro / vintage": 3, "atelier d'artisan": 4,
    "privatisé": 3, "coucher de soleil": 3, "sensations": 3, "bohème": 3,
}
_CURATED = {"paris_zigzag": 12, "selections_couple": 12, "selections_squad": 12, "paris_secret": 10, "le_bonbon": 8, "time_out": 6, "paris_friendly": 6, "paris_city_game": 6}
# Classics every visitor does: good, but nothing to tell.
_COMMON = re.compile(
    r"tour eiffel|bateaux?[- ]mouches?|bateaux parisiens|croisière (?:commentée|d'une heure)|louvre|arc de triomphe|"
    r"moulin rouge|lido|musée d'orsay|sacré[- ]c(?:œ|oe)ur|big bus|tootbus|city ?tour|bus panoramique|coupe[- ]file|"
    r"billet d'entrée|visite guidée classique|hop[- ]on",
)
_BIG_VENUE = re.compile(r"accor arena|z[ée]nith|stade|la défense arena|palais des congrès|olympia\b|bercy")
_CHAIN = re.compile(r"\b(?:hippopotamus|buffalo grill|big mamma|pny|five guys|léon de bruxelles|pizza hut|bistro r[ée]gent|au bureau|o'sullivans)\b")
_GENERIC_CUISINE = re.compile(r"\b(?:pizza|burger|sushi|kebab|fast food|coffee shop|sandwich)\b")


@dataclass
class Originality:
    score: int
    reasons: list[str] = field(default_factory=list)


class Scorer:
    """Scores activities against the base they belong to (tag rarity)."""

    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.tag_counts: Counter[str] = Counter()
        for item in items:
            self.tag_counts.update(describe(item["activity"])["tags"])
        self.total = max(1, len(items))

    def score(self, item: dict[str, Any], found: dict[str, list[str]] | None = None, keywords: list[str] | None = None) -> Originality:
        activity = item["activity"]
        found = found or describe(activity)
        if keywords is None:
            keywords = (item.get("enrichment") or {}).get("keywords")
        if keywords is None:  # not stored yet: read the texts
            keywords = extract(texts(item))
        value, reasons = 30.0, []
        venue = ((activity.get("venue") or {}).get("name") or "").lower()
        title = f"{activity.get('title') or ''} {venue}".lower()
        # A classic's boat or view is what everyone does: no bonus for its setting nor its rarity here.
        common = bool(_COMMON.search(title))

        categories = set(activity.get("categories") or [])
        nature = {
            t.replace("_", " "): _NATURE[t] for t in found["tags"]
            if t in _NATURE and not (common and t in ("vue", "sur_l_eau")) and not (t in _WORKSHOP and {"restaurant", "bar"} & categories)
        }
        text = texts(item).lower()
        nature |= {label: points for label, points, matches in _NATURE_TEXTS if label not in nature and matches(text)}
        if _SETTING.search(title):
            nature["château, manoir"] = 16
        if nature:
            # The most unusual of what it is, and half the next: a murder party in a hidden place, a Halloween night in a
            # castle, a karaoke with performers.
            best = sorted(nature.items(), key=lambda pair: -pair[1])
            value += min(40, best[0][1] + (best[1][1] / 2 if len(best) > 1 else 0))
            reasons.append("hors du quotidien : " + ", ".join(label for label, _ in best[:2]))
        if "lieu_insolite" in categories:
            value += 10
            reasons.append("lieu insolite")

        rarest = min((self.tag_counts[t] for t in found["tags"]), default=None)
        if rarest and not common:
            # 1 activity like it in the base: +15; one in ten: about +5; very common: 0.
            rarity = 1 - math.log(rarest) / math.log(self.total)
            value += round(15 * max(0.0, rarity) ** 2, 1)
            if rarest <= self.total * 0.005:
                reasons.append("rare dans la base")

        words = [w for w in keywords if w in _OFFBEAT_WORDS]
        if words:
            value += min(16, sum(_OFFBEAT_WORDS[w] for w in words))
            reasons.append("décrit comme " + ", ".join(words[:3]))

        if points := _CURATED.get(item["source_id"]):
            value += points
            reasons.append("repéré par un média de curation")

        if activity.get("kind") == "temporary" and "éphémère" not in words:
            value += 3

        if common:
            value -= 18
            reasons.append("classique touristique")
        if _BIG_VENUE.search(venue):
            value -= 12
            reasons.append("grande salle")
        # Only for places to eat or drink: a tour's meeting point may be "in front of Five Guys".
        if {"restaurant", "bar"} & categories and _CHAIN.search(title):
            value -= 20
            reasons.append("chaîne")
        if "restaurant" in categories and _GENERIC_CUISINE.search(title):
            value -= 8
            reasons.append("cuisine courante")
        return Originality(max(0, min(100, round(value))), reasons)


def main() -> None:
    from surprise.local_store import open_store

    with open_store() as store:
        items = [item for item in store.list_for_moderation() if item["status"] not in ("filtered", "rejected")]
    scorer = Scorer(items)
    scored = sorted(((scorer.score(item), item) for item in items), key=lambda pair: -pair[0].score)
    buckets = Counter(min(9, s.score // 10) for s, _ in scored)
    print(f"{len(scored)} activités\n\nRépartition :")
    for bucket in range(10):
        print(f"  {bucket * 10:>3}-{bucket * 10 + 9:<3} {'█' * (buckets[bucket] * 60 // max(1, max(buckets.values())))} {buckets[bucket]}")
    print("\nLes plus originales :")
    for originality, item in scored[:25]:
        print(f"  {originality.score:>3}  {item['activity']['title'][:60]:60}  {'; '.join(originality.reasons)[:80]}")
    print("\nLes plus classiques :")
    for originality, item in scored[-8:]:
        print(f"  {originality.score:>3}  {item['activity']['title'][:60]:60}  {'; '.join(originality.reasons)[:80]}")


if __name__ == "__main__":
    main()
