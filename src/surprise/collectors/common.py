"""Pieces shared by the collectors: normalization result, parsing helpers, command line."""

import argparse
import re
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal

from pydantic import HttpUrl, TypeAdapter, ValidationError

from surprise.models import Activity, RawRecord

_url = TypeAdapter(HttpUrl)
_EUROS = re.compile(r"(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?)", re.IGNORECASE)
# "de 24 à 45 €": the lower bound carries no currency sign.
_EURO_RANGE = re.compile(r"(\d+(?:[.,]\d{1,2})?)\s*(?:à|-|–)\s*\d+(?:[.,]\d{1,2})?\s*(?:€|euros?)", re.IGNORECASE)


@dataclass
class Normalized:
    raw: RawRecord
    activity: Activity | None = None
    rejection: str | None = None


def safe_url(value: str | None) -> HttpUrl | None:
    try:
        return _url.validate_python(value.strip()) if value else None
    except ValidationError:
        return None


def euro_amounts(text: str | None) -> list[Decimal]:
    """Amounts in euros mentioned in a price text, sorted."""
    text = text or ""
    found = _EUROS.findall(text) + _EURO_RANGE.findall(text)
    return sorted({Decimal(a.replace(",", ".")) for a in found})


def run(description: str, collect: Callable[[], Iterable[Normalized]]) -> None:
    """Command line shared by the collectors: summary, then optional storage."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--store",
        choices=["local", "supabase"],
        help="local : data/surprise.db (SQLite) ; supabase : payloads bruts dans raw_records",
    )
    args = parser.parse_args()

    results = list(collect())
    kept = [r for r in results if r.activity]
    print(f"{len(results)} fiches, {len(kept)} retenues, {sum(bool(r.activity.is_evening) for r in kept)} en soirée")
    for reason, count in Counter(r.rejection for r in results if r.rejection).most_common():
        print(f"  rejet — {reason} : {count}")

    if args.store == "local":
        from surprise.local_store import DEFAULT_PATH, LocalStore

        with LocalStore() as store:
            added = store.save_raw_records([r.raw for r in results])
            store.save_normalized([(r.raw, r.activity, r.rejection) for r in results])
        print(f"{added} nouveaux payloads bruts dans {DEFAULT_PATH}")
    elif args.store == "supabase":
        from surprise.store import SupabaseStore

        with SupabaseStore.from_env() as store:
            print(f"{store.save_raw_records([r.raw for r in results])} payloads bruts envoyés")
