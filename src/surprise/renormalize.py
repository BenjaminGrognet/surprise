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

import httpx

from surprise.booking import PageChecks
from surprise.collectors.common import USER_AGENT, require_booking, split_reasons
from surprise.collectors.facts import utc_now
from surprise.local_store import LocalStore, open_store


def renormalize(store: LocalStore, sources: list[str] | None = None, rejections: list[str] | None = None) -> Counter:
    """Normalizes the chosen records again and saves them; the count of changes ("rejet → retenue")."""
    rows = [row for row in store.raw_with_rejection() if (not sources or row[0] in sources) and (not rejections or set(split_reasons(row[2])) & set(rejections))]
    print(f"{len(rows)} fiches à normaliser de nouveau")
    now, changes, results, checks = utc_now(), Counter(), [], PageChecks(store.page_checks())
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        for index, (source_id, payload, before) in enumerate(rows, 1):
            try:
                normalize = importlib.import_module(f"surprise.collectors.{source_id}").normalize
            except (ImportError, AttributeError):
                continue
            arguments = (json.loads(payload), now) if "now" in inspect.signature(normalize).parameters else (json.loads(payload),)
            result = require_booking(client, normalize(*arguments), checks)
            results.append(result)
            changes[f"{before or 'retenue'} → {result.rejection or 'retenue'}"] += 1
            if index % 200 == 0:
                store.save_normalized([(r.raw, r.activity, r.rejection) for r in results])
                results = []
                print(f"  {index}/{len(rows)}")
    store.save_normalized([(r.raw, r.activity, r.rejection) for r in results])
    store.save_page_checks(checks.new)
    return changes


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
