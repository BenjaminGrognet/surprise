"""Write tests/fixtures/catalogue.json: real activities of the base, one neighbourhood's, for the tests that want
the evenings as the couple gets them (tests/real_catalogue.py). Reads the base only.

    uv run --env-file .env python tests/snapshot_catalogue.py

The activities with a description of their own that would be steps on DAY for a few wishes, around the place where they are the densest; with
their originality as the whole base scores it, and their genres read before the media's texts are taken out
(lead_text, site_excerpt: not to be published). Images are the sites' own, loaded live by the tests.
"""

import argparse
import copy
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from surprise import parcours, quiz  # noqa: E402
from surprise.local_store import open_store  # noqa: E402
from test_quiz import ANSWERS  # noqa: E402

DAY = date(2026, 10, 9)  # a Friday: the tests' day (test_parcours.DAY), others take it a few weeks on
PATH = Path(__file__).parent / "fixtures" / "catalogue.json"
WISHES = [(["rire"], False), (["rire"], True), (["romantique"], True), (["jouer"], False), (["musique"], False), (["fete"], False)]
RADIUS_KM = 1.5
PER_ROLE = 25  # best activities kept for each part of the evening, for each wish


class NoCache:
    """The tests' store: no engine answer cached (the API runs there with checks=0)."""

    def cached_availability(self, *args: Any) -> dict:
        return {}


def requests(day: date = DAY) -> list[parcours.Request]:
    profile = quiz.profile_from(ANSWERS)
    return [quiz.requests_for(profile, [day], envies, dinner=dinner)[0] for envies, dinner in WISHES]


def select(base: parcours.Base) -> list[dict[str, Any]]:
    """The activities kept: for each wish, the best of each part of the evening near the densest place."""
    asked = [(request, parcours.candidates_for(NoCache(), base, request, checks=0)) for request in requests()]
    every = [c for _, candidates in asked for c in candidates if c.lat is not None]
    centre = max(
        ((c.lat, c.lon) for c in every),
        key=lambda point: sum(1 for c in every if parcours.distance_km(point, (c.lat, c.lon)) <= RADIUS_KM),
    )
    keys: dict[tuple[str, str], None] = {}
    for _, candidates in asked:
        # Only those with a description of their own: a media's text is not kept.
        near = [
            c for c in candidates if c.lat is not None and parcours.distance_km(centre, (c.lat, c.lon)) <= RADIUS_KM
            and c.item["enrichment"].get("description")
        ]
        for part in {c.role for c in near}:
            for c in sorted((c for c in near if c.role == part), key=lambda c: -c.score)[:PER_ROLE]:
                keys[c.key] = None
    print(f"centre {centre[0]:.4f}, {centre[1]:.4f} : {len(keys)} activités")
    return [base.by_key[key] for key in keys]


def public(item: dict[str, Any], originality: int) -> dict[str, Any]:
    """The activity as the tests read it: its genres fixed, the media's texts out, the moderation's fields out."""
    genres = parcours.item_genres(item)
    kept = {k: copy.deepcopy(item[k]) for k in ("source_id", "external_id", "status", "source_url", "source_genre", "activity", "enrichment")}
    kept["enrichment"]["site_excerpt"] = None
    return kept | {"lead_text": None, "cover_url": item.get("cover_url"), "genres": genres, "originality": originality}


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrait de vraies activités de la base pour les tests")
    parser.parse_args()
    with open_store() as store:
        base = parcours.Base.load(store)
    items = [public(item, base.originality[(item["source_id"], item["external_id"])]) for item in select(base)]
    PATH.parent.mkdir(exist_ok=True)
    PATH.write_text(json.dumps({"day": DAY.isoformat(), "items": items}, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(f"{PATH} : {len(items)} activités, {Counter(i['source_id'] for i in items).most_common()}")


if __name__ == "__main__":
    main()
