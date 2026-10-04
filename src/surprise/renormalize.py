"""Normalize the stored pages again: rules changed, nothing to download but the booking checks.

Each raw payload kept in the store goes through its collector's normalization
again, then through the booking rule (surprise.booking), as at the collection.
Chosen by source and by rejection, to recover what a new rule now accepts.

    uv run python -m surprise.renormalize --rejet "hors Paris intra-muros" --rejet "ni gratuit ni réservable en ligne"
    uv run python -m surprise.renormalize --source tiqets
"""

import argparse
import importlib
import inspect
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import batched

import httpx

from surprise import enrich
from surprise.booking import PageChecks
from surprise.collectors.common import USER_AGENT, require_booking, split_reasons
from surprise.collectors.facts import utc_now
from surprise.local_store import LocalStore, open_store

BATCH = 200  # records saved at once
WORKERS = 32  # records checked at once, one page at a time per site (PageChecks)


def renormalize(store: LocalStore, sources: list[str] | None = None, rejections: list[str] | None = None) -> Counter:
    """Normalizes the chosen records again and saves them; the count of changes ("rejet → retenue").

    The booking checks run in parallel; the records are saved by batches as they are done, a slow site holding
    back none of the others.
    """
    rows = [row for row in store.raw_with_rejection() if (not sources or row[0] in sources) and (not rejections or set(split_reasons(row[2])) & set(rejections))]
    normalizers = {source_id: _normalizer(source_id) for source_id in {row[0] for row in rows}}
    rows = [row for row in rows if normalizers[row[0]]]
    print(f"{len(rows)} fiches à normaliser de nouveau", flush=True)
    now, changes, checks = utc_now(), Counter(), PageChecks(store.page_checks())
    # The addresses OpenStreetMap gave are not asked again (Nominatim answers one request per second).
    enrich.load_answers(store)

    def again(row: tuple[str, str, str | None]):
        source_id, payload, before = row
        normalize = normalizers[source_id]
        arguments = (json.loads(payload), now) if "now" in inspect.signature(normalize).parameters else (json.loads(payload),)
        return before, require_booking(client, normalize(*arguments), checks)

    done = 0
    with (
        httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client,
        ThreadPoolExecutor(WORKERS) as pool,
    ):
        for batch in batched(as_completed([pool.submit(again, row) for row in rows]), BATCH):
            results = [future.result() for future in batch]
            store.save_normalized([(r.raw, r.activity, r.rejection) for _, r in results])
            # Saved as it goes: an interrupted run keeps the pages it has read.
            store.save_page_checks(checks.take_new())
            enrich.save_answers(store)
            changes.update(f"{before or 'retenue'} → {r.rejection or 'retenue'}" for before, r in results)
            done += len(batch)
            print(f"  {done}/{len(rows)}", flush=True)
    return changes


def _normalizer(source_id: str):
    try:
        return importlib.import_module(f"surprise.collectors.{source_id}").normalize
    except (ImportError, AttributeError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", action="append", help="ne traiter que cette source (répétable)")
    parser.add_argument("--rejet", action="append", help="ne traiter que les fiches écartées pour ce motif (répétable)")
    parser.add_argument("--db", help="base SQLite ou URL postgresql:// (défaut : SUPABASE_DB_URL, sinon data/surprise.db)")
    args = parser.parse_args()
    sys.stdout.reconfigure(errors="replace")
    with open_store(args.db) as store:
        changes = renormalize(store, args.source, args.rejet)
    for change, count in changes.most_common():
        print(f"  {change} : {count}")


if __name__ == "__main__":
    main()
