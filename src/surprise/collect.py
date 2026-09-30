"""Collect the sources together, a few at a time, each saved as it goes (surprise.collectors.common.collect_source).

Pages read less than a week ago are not read again: their stored payloads are normalized anew (dates, rules).
A failing source is reported and the others go on. Nominatim stays at 1 request/s: its lock is shared.

    uv run --env-file .env python -m surprise.collect --limit 50
    uv run --env-file .env python -m surprise.collect --source fever --source tiqets --refresh
"""

import argparse
import importlib
import sys
import time as clock
import traceback
from concurrent.futures import ThreadPoolExecutor

from surprise.collectors.common import collect_source, print_counts
from surprise.local_store import open_store

SOURCES = [
    "que_faire_a_paris", "paris_zigzag", "funbooker", "paris_friendly", "paris_city_game", "come_to_paris",
    "paris_secret", "concerts_paris", "paris_jetaime", "paris_jetaime_billetterie", "visit_paris_region",
    "explore_paris", "wecandoo", "fever", "getyourguide", "tiqets", "civitatis", "eventbrite", "shotgun",
    "billetreduc", "time_out", "le_bonbon", "selections_couple", "osm_restaurants", "time_out_hotels",
    "nuits_couple", "sortir_a_paris", "dice", "escape_game", "osm_loisirs",
]


def collect_one(source_id: str, args: argparse.Namespace) -> tuple[str, object]:
    """(source, counts), or (source, the error): one source failing leaves the others."""
    started = clock.monotonic()
    log = lambda message: print(f"[{source_id}] {message}", flush=True)  # noqa: E731
    try:
        module = importlib.import_module(f"surprise.collectors.{source_id}")
        with open_store(args.db) as store:
            counts = collect_source(source_id, module._collect_with_client, store, args.limit, args.refresh, args.minutes, log)
        log(f"terminé en {clock.monotonic() - started:.0f} s")
        return source_id, counts
    except Exception as error:  # noqa: BLE001
        log(f"échec : {error!r}\n{traceback.format_exc()}")
        return source_id, error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", action="append", choices=SOURCES, help="ne collecter que cette source (répétable)")
    parser.add_argument("--limit", type=int, help="nombre maximum de fiches lues par source (les pages encore fraîches ne comptent pas)")
    parser.add_argument("--refresh", action="store_true", help="relire aussi les pages lues il y a moins d'une semaine")
    parser.add_argument("--minutes", type=float, help="temps maximum par source (ce qui est lu est enregistré)")
    parser.add_argument("--jobs", type=int, default=4, help="sources collectées en même temps (défaut : 4)")
    parser.add_argument("--db", help="base SQLite ou URL postgresql:// (défaut : SUPABASE_DB_URL, sinon data/surprise.db)")
    args = parser.parse_args()
    sys.stdout.reconfigure(errors="replace")

    with ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(lambda source_id: collect_one(source_id, args), args.source or SOURCES))
    print("\nBilan", flush=True)
    for source_id, outcome in results:
        if isinstance(outcome, Exception):
            print(f"[{source_id}] échec : {outcome!r}", flush=True)
        else:
            print_counts(outcome, f"[{source_id}] ")
    sys.exit(any(isinstance(outcome, Exception) for _, outcome in results))


if __name__ == "__main__":
    main()
