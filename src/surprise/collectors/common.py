"""Pieces shared by the collectors: normalization result, parsing helpers, command line."""

import argparse
import json
import os
import re
import sys
import time as clock
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import dataclass
from decimal import Decimal
from itertools import batched, islice
from typing import Any

import httpx
from pydantic import HttpUrl, TypeAdapter, ValidationError

from surprise.booking import PageChecks, booking_engine, booking_urls, is_free, is_open, is_walk_in
from surprise.models import Activity, Offer, RawRecord

USER_AGENT = "surprise-collector/0.1"
# Fiches saved together; booking pages read at once (one at a time per site).
BATCH = 50
CHECK_WORKERS = 16
_url = TypeAdapter(HttpUrl)
# A booking or ticketing link, by its text ("Réservez") or its domain.
BOOKING = re.compile(
    r"r[ée]serv|billet|ticket|booking|\bbook\b|tickeasy|fnacspectacles|eventbrite|shotgun|dice\.fm|weezevent|"
    r"themisweb|seetickets|feverup|placeminute|billetreduc|mapado|billetweb|helloasso",
    re.IGNORECASE,
)
# Not an outing: shops, beauty treatments, wellness products.
OFF_TOPIC = re.compile(
    r"soins? (?:du |de )?visage|hydrafacial|skincare|épilation|manucure|pédicure|coiffure|coiffeur|maquillage|"
    r"massage prénatal|flagship|boutique|concept[- ]store|magasin|shopping|\bcures?\b",
    re.IGNORECASE,
)
# Offers for a stag or hen party, or for girls only, in their title: a group of friends, not a couple. Their texts
# often say "also for a hen party" of fine couple workshops: those are kept.
GROUP_PARTY = re.compile(
    r"\bEVG\b|\bEVJF\b|enterrements? de vie de (?:garçon|jeune fille|célibataires?)|bachelor(?:ette)? party|hen party|stag party|girls only|ladies only|entre filles",
    re.IGNORECASE,
)
_EUROS = re.compile(r"(?<!\d)(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?)", re.IGNORECASE)
# "de 24 à 45 €": the lower bound carries no currency sign.
_EURO_RANGE = re.compile(r"(?<!\d)(\d+(?:[.,]\d{1,2})?)\s*(?:à|-|–)\s*\d+(?:[.,]\d{1,2})?\s*(?:€|euros?)", re.IGNORECASE)


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


def require_booking(client: httpx.Client, result: Normalized, checks: PageChecks | None = None) -> Normalized:
    """Only free activities, or ones bookable through a known ticketing or booking site, are kept.

    Bars, clubs and restaurants are kept while open, marked not bookable online when they are not.
    Rejected activities keep their normalization, to be reviewed apart in moderation.
    """
    activity = result.activity
    if not activity or result.rejection or is_free(activity):
        return result
    checks = checks or PageChecks()
    if booking_engine(client, booking_urls(activity), checks):
        return result
    if is_walk_in(activity):
        if not is_open(client, activity, json.dumps(result.raw.payload, ensure_ascii=False), checks):
            return Normalized(result.raw, activity, "fermé définitivement")
        offers = [offer.model_copy(update={"online_booking": False}) for offer in activity.offers] or [Offer(online_booking=False)]
        return Normalized(result.raw, activity.model_copy(update={"offers": offers}))
    return Normalized(result.raw, activity, "ni gratuit ni réservable en ligne")


# Pages read at a previous run, still fresh (by URL): run() fills it from the store, page() reads from it.
_fresh: dict[str, list[dict[str, Any]]] = {}


def remembered(url: str, read: Callable[[], Any], modified: str | None = None) -> list[dict[str, Any]]:
    """What a page gives (payloads): the stored ones while fresh and not `modified` since, else read() — None if unreadable.

    Each payload keeps its page ("_page"), for the next run to skip it.
    """
    stored = _fresh.get(url)
    if stored and all(payload.get("_modified") == modified for payload in stored):
        return stored
    found = read()
    found = [] if found is None else [found] if isinstance(found, dict) else found
    for payload in found:
        payload["_page"] = url
        if modified:
            payload["_modified"] = modified
    return found


def page(
    client: httpx.Client, url: str, parse: Callable[[httpx.Response], Any], delay: float = 0.0, modified: str | None = None
) -> list[dict[str, Any]]:
    """The payloads parse() finds in a detail page, read after the polite delay unless it is still fresh."""

    def read() -> Any:
        clock.sleep(delay)
        try:
            response = client.get(url)
        except httpx.HTTPError:
            return None
        return parse(response) if response.status_code == 200 else None

    return remembered(url, read, modified)


def collect_source(
    source_id: str,
    collect: Callable[[], Iterable[Normalized]],
    store: Any = None,
    limit: int | None = None,
    refresh: bool = False,
    minutes: float | None = None,
    log: Callable[[str], None] = lambda message: print(message, flush=True),
) -> Counter:
    """Collect a source into the store, saved as it goes, by batches: the booking checks of a batch run in parallel.

    Pages read less than a week ago are not read again (unless `refresh`), nor booking pages less than a month ago.
    """
    started = clock.monotonic()
    if store and not refresh:
        # Each source says how long its pages stay fresh: a concert changes sooner than a restaurant.
        days = getattr(sys.modules[collect.__module__], "FRESH_DAYS", None)
        _fresh.update(store.fresh_pages(source_id, days) if days else store.fresh_pages(source_id))
    checks = PageChecks(store.page_checks() if store else None)
    counts: Counter = Counter()
    with (
        httpx.Client(timeout=15, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client,
        ThreadPoolExecutor(CHECK_WORKERS) as pool,
    ):
        for batch in batched(islice(collect(), limit), BATCH):
            results = list(pool.map(lambda result: require_booking(client, result, checks), batch))
            if store:
                store.save_raw_records([r.raw for r in results if not r.raw.payload.get("_cached")])
                store.save_normalized([(r.raw, r.activity, r.rejection) for r in results])
                store.save_page_checks(checks.new)
                checks.new = {}
            for r in results:
                counts["fiches"] += 1
                counts["pages déjà fraîches"] += bool(r.raw.payload.get("_cached"))
                counts["retenues" if r.activity and not r.rejection else f"rejet — {r.rejection}"] += 1
            log(f"{counts['fiches']} fiches ({counts['retenues']} retenues), {clock.monotonic() - started:.0f} s")
            if minutes and clock.monotonic() - started > minutes * 60:
                log(f"arrêt : plus de {minutes} min")
                break
    return counts


def run(description: str, collect: Callable[[], Iterable[Normalized]]) -> None:
    """Command line shared by the collectors: summary, then optional storage."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--store",
        choices=["local", "supabase"],
        help="local : data/surprise.db (SQLite) ; supabase : les mêmes tables dans Supabase (SUPABASE_DB_URL)",
    )
    parser.add_argument("--limit", type=int, help="nombre maximum de fiches lues (les pages suivantes ne sont pas chargées)")
    parser.add_argument("--refresh", action="store_true", help="relire aussi les pages lues il y a moins d'une semaine")
    parser.add_argument("--minutes", type=float, help="s'arrêter après ce temps (ce qui est lu est enregistré)")
    args = parser.parse_args()

    from surprise.local_store import LocalStore, PostgresStore

    source_id = sys.modules[collect.__module__].SOURCE_ID
    store = (LocalStore() if args.store == "local" else PostgresStore(os.environ["SUPABASE_DB_URL"])) if args.store else None
    with store or nullcontext():
        counts = collect_source(source_id, collect, store, args.limit, args.refresh, args.minutes)
    print_counts(counts)


def print_counts(counts: Counter, prefix: str = "") -> None:
    print(f"{prefix}{counts['fiches']} fiches, {counts['retenues']} retenues, {counts['pages déjà fraîches']} déjà fraîches", flush=True)
    for reason, count in counts.most_common():
        if reason.startswith("rejet"):
            print(f"{prefix}  {reason} : {count}", flush=True)
