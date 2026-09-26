"""Evenings checked ahead: every activity whose booking engine answers for a date, for the coming evenings.

A composition only asks a few engines live (quiz --checks): the workshops, spas,
escape games and tables that were not asked then could not be steps. Run each
night after the collection, this asks them all for the next days; the evenings
composed meanwhile read these answers (parcours.CACHE_HOURS).

Activities without an engine that surprise.availability can ask are probed on
the first evening only, not again for the next ones.

    uv run python -m surprise.prefetch --jours 14
"""

import argparse
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from surprise import parcours
from surprise.local_store import DEFAULT_PATH, LocalStore


def prefetch(store: LocalStore, days: list[date], party: int = 2) -> Counter:
    """Engine answers for each day, saved in the store; the count of answers by outcome."""
    base = parcours.Base.load(store)
    items = [item for item in base.items if parcours.needs_check(item)]
    print(f"{len(items)} activités à vérifier sur {len(days)} soirs")
    totals: Counter = Counter()
    for day in days:
        start, end = parcours.window(day, "18:00", "02:00")
        request = parcours.Request(day=day, budget=0, start=start, end=end, vibes=[], party=party)
        answers = parcours.check_engines(store, items, request, limit=len(items), prescore={})
        outcomes = Counter(
            "sans moteur" if not a["engine"] else {True: "libres", False: "complètes", None: "inconnues"}[a["available"]]
            for key, a in answers.items()
        )
        print(f"{day:%a %d/%m} : " + ", ".join(f"{n} {label}" for label, n in outcomes.most_common()))
        totals += outcomes
        # No engine to ask: not probed again for the next evenings.
        no_engine = {key for key, a in answers.items() if not a["engine"]}
        items = [item for item in items if (item["source_id"], item["external_id"]) not in no_engine]
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jours", type=int, default=14, help="soirs à vérifier à partir d'aujourd'hui (14 par défaut)")
    parser.add_argument("--party", type=int, default=2)
    parser.add_argument("--db", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    sys.stdout.reconfigure(errors="replace")
    today = date.today()
    with LocalStore(args.db) as store:
        prefetch(store, [today + timedelta(days=n) for n in range(args.jours)], args.party)


if __name__ == "__main__":
    main()
