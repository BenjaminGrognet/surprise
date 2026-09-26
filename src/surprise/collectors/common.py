"""Pieces shared by the collectors: normalization result, parsing helpers, command line."""

import argparse
import json
import re
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from itertools import islice

import httpx
from pydantic import HttpUrl, TypeAdapter, ValidationError

from surprise.booking import booking_engine, booking_urls, is_free, is_open, is_walk_in
from surprise.models import Activity, Offer, RawRecord

USER_AGENT = "surprise-collector/0.1"
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


def require_booking(client: httpx.Client, result: Normalized) -> Normalized:
    """Only free activities, or ones bookable through a known ticketing or booking site, are kept.

    Bars, clubs and restaurants are kept while open, marked not bookable online when they are not.
    Rejected activities keep their normalization, to be reviewed apart in moderation.
    """
    activity = result.activity
    if not activity or result.rejection or is_free(activity):
        return result
    if booking_engine(client, booking_urls(activity)):
        return result
    if is_walk_in(activity):
        if not is_open(client, activity, json.dumps(result.raw.payload, ensure_ascii=False)):
            return Normalized(result.raw, activity, "fermé définitivement")
        offers = [offer.model_copy(update={"online_booking": False}) for offer in activity.offers] or [Offer(online_booking=False)]
        return Normalized(result.raw, activity.model_copy(update={"offers": offers}))
    return Normalized(result.raw, activity, "ni gratuit ni réservable en ligne")


def run(description: str, collect: Callable[[], Iterable[Normalized]]) -> None:
    """Command line shared by the collectors: summary, then optional storage."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--store",
        choices=["local", "supabase"],
        help="local : data/surprise.db (SQLite) ; supabase : payloads bruts dans raw_records",
    )
    parser.add_argument("--limit", type=int, help="nombre maximum de fiches lues (les pages suivantes ne sont pas chargées)")
    args = parser.parse_args()

    results = list(islice(collect(), args.limit))
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        results = [require_booking(client, r) for r in results]
    kept = [r for r in results if r.activity and not r.rejection]
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
