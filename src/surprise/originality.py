"""Originality: how unusual an activity is, from 0 (seen everywhere) to 100 (a story to tell).

The score adds up explainable signals, each with its reason, so it can be
tuned like the tags:
- what the activity is: tags of offbeat places and experiences (hidden bar,
  underground, in the dark, flotation, immersive), "lieu insolite" category;
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
from surprise.tags import describe

_OFFBEAT_TAGS = {
    "cache": 14, "souterrain": 14, "dans_le_noir": 16, "flottaison": 14, "defouloir": 12, "immersif": 10,
    "frisson": 6, "sur_l_eau": 5, "vue": 4, "chandelles": 6, "drag": 8, "magie": 6, "cirque": 5,
    "murder_party": 8, "escape_game": 4, "jeu_de_piste": 6, "artisanat": 5, "parfum_bougie": 5, "shooting": 5,
}
_OFFBEAT_WORDS = {
    "insolite": 8, "secret": 8, "mystérieux": 5, "immersif": 5, "interactif": 4, "éphémère": 5,
    "cave voûtée": 5, "dans le noir": 6, "aux chandelles": 4, "rétro / vintage": 3, "atelier d'artisan": 4,
    "privatisé": 3, "coucher de soleil": 3, "sensations": 3, "bohème": 3,
}
_CURATED = {"paris_zigzag": 12, "selections_couple": 12, "paris_secret": 10, "le_bonbon": 8, "time_out": 6, "paris_friendly": 6, "paris_city_game": 6}
# Classics every visitor does: good, but nothing to tell.
_COMMON = re.compile(
    r"tour eiffel|bateaux?[- ]mouches?|bateaux parisiens|croisière (?:commentée|d'une heure)|louvre|arc de triomphe|"
    r"moulin rouge|lido|musée d'orsay|sacré[- ]c(?:œ|oe)ur|big bus|tootbus|city ?tour|bus panoramique|coupe[- ]file|"
    r"billet d'entrée|visite guidée classique|hop[- ]on",
    re.IGNORECASE,
)
_BIG_VENUE = re.compile(r"accor arena|z[ée]nith|stade|la défense arena|palais des congrès|olympia\b|bercy", re.IGNORECASE)
_CHAIN = re.compile(r"\b(?:hippopotamus|buffalo grill|big mamma|pny|five guys|léon de bruxelles|pizza hut|bistro r[ée]gent|au bureau|o'sullivans)\b", re.IGNORECASE)
_GENERIC_CUISINE = re.compile(r"\b(?:pizza|burger|sushi|kebab|fast food|coffee shop|sandwich)\b", re.IGNORECASE)


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
        venue = (activity.get("venue") or {}).get("name") or ""
        title = f"{activity.get('title') or ''} {venue}"
        # A classic's boat or view is what everyone does: no bonus for its setting nor its rarity here.
        common = bool(_COMMON.search(title))

        offbeat = sorted(
            ((_OFFBEAT_TAGS[t], t) for t in found["tags"] if t in _OFFBEAT_TAGS and not (common and t in ("vue", "sur_l_eau"))),
            reverse=True,
        )
        if offbeat:
            value += min(24, sum(points for points, _ in offbeat))
            reasons.append("cadre ou expérience insolite : " + ", ".join(t.replace("_", " ") for _, t in offbeat[:2]))
        if "lieu_insolite" in (activity.get("categories") or []):
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
        if {"restaurant", "bar"} & set(activity.get("categories") or []) and _CHAIN.search(title):
            value -= 20
            reasons.append("chaîne")
        if "restaurant" in (activity.get("categories") or []) and _GENERIC_CUISINE.search(title):
            value -= 8
            reasons.append("cuisine courante")
        return Originality(max(0, min(100, round(value))), reasons)


def main() -> None:
    from surprise.local_store import LocalStore

    with LocalStore() as store:
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
