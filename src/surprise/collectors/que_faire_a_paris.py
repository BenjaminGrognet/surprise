"""Collector for Que Faire à Paris (Ville de Paris open data, ODbL).

API: Opendatasoft Explore v2.1, dataset ``que-faire-a-paris-``.
The export endpoint returns every matching record in one call (the records
endpoint caps offset + limit at 10 000). ``OPENDATA_PARIS_URL`` overrides the
portal, e.g. the Opendatasoft mirror https://parisdata.opendatasoft.com when
opendata.paris.fr does not resolve.
"""

import argparse
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterator
from zoneinfo import ZoneInfo

import httpx
from pydantic import HttpUrl, TypeAdapter, ValidationError

from surprise.models import Activity, ActivityKind, Occurrence, Offer, RawRecord, Venue

SOURCE_ID = "que_faire_a_paris"
DATASET = "que-faire-a-paris-"
DEFAULT_BASE_URL = "https://opendata.paris.fr"
PARIS = ZoneInfo("Europe/Paris")
WINDOW = timedelta(weeks=6)
# An occurrence counts as an evening one if it is still running at this hour.
EVENING_FROM = time(19, 0)

_url = TypeAdapter(HttpUrl)
_CHILD_AUDIENCE = re.compile(r"enfant|jeune public|famille|b[ée]b[ée]", re.IGNORECASE)
_ADULT_AUDIENCE = re.compile(r"adulte", re.IGNORECASE)
_CHILD_TAGS = {"enfants", "jeune public", "famille"}
_EUROS = re.compile(r"(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?)", re.IGNORECASE)


@dataclass
class Normalized:
    raw: RawRecord
    activity: Activity | None = None
    rejection: str | None = None


def fetch(client: httpx.Client, today: date, window: timedelta = WINDOW) -> list[dict[str, Any]]:
    """Events still running today and starting within the window."""
    where = f"date_end >= date'{today.isoformat()}' and date_start <= date'{(today + window).isoformat()}'"
    response = client.get(export_url(), params={"where": where, "timezone": "Europe/Paris"})
    response.raise_for_status()
    return response.json()


def export_url() -> str:
    base_url = os.environ.get("OPENDATA_PARIS_URL") or DEFAULT_BASE_URL
    return f"{base_url.rstrip('/')}/api/explore/v2.1/catalog/datasets/{DATASET}/exports/json"


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(
        source_id=SOURCE_ID,
        external_id=str(payload.get("event_id") or payload["id"]),
        url=_safe_url(payload.get("url")),
        payload=payload,
    )


def normalize(payload: dict[str, Any], now: datetime, window: timedelta = WINDOW) -> Normalized:
    raw = to_raw_record(payload)

    if reason := _youth_audience(payload):
        return Normalized(raw, rejection=reason)

    try:
        venue = Venue(
            name=payload.get("address_name") or payload.get("contact_organisation_name") or "Lieu inconnu",
            address=payload.get("address_street"),
            postal_code=str(payload.get("address_zipcode") or ""),
            latitude=(payload.get("lat_lon") or {}).get("lat"),
            longitude=(payload.get("lat_lon") or {}).get("lon"),
            website=_safe_url(payload.get("address_url")),
        )
    except ValidationError:
        return Normalized(raw, rejection="hors Paris intra-muros")

    all_occurrences = parse_occurrences(payload.get("occurrences"))
    occurrences = [o for o in all_occurrences if _in_window(o, now, window)]

    try:
        activity = Activity(
            title=payload["title"].strip(),
            # Descriptions are rewritten during enrichment, never copied from the source.
            description=None,
            kind=ActivityKind.TEMPORARY,
            # date_start/date_end are shifted by 1-3 h and can land on the next day:
            # the occurrences are the reliable source, the fields a fallback.
            starts_on=min((o.starts_at.date() for o in all_occurrences), default=_date(payload.get("date_start"))),
            ends_on=max(
                ((o.ends_at or o.starts_at).date() for o in all_occurrences), default=_date(payload.get("date_end"))
            ),
            website=_safe_url(payload.get("contact_url")) or _safe_url(payload.get("url")),
            is_evening=is_evening(occurrences),
            venue=venue,
            occurrences=occurrences,
            offers=[parse_offer(payload)],
        )
    except (KeyError, ValidationError) as error:
        return Normalized(raw, rejection=f"invalide : {error}")

    return Normalized(raw, activity=activity)


def parse_occurrences(value: str | None) -> list[Occurrence]:
    """Parse ``start_end;start_end`` ISO 8601 pairs, skipping malformed ones.

    The wall-clock time is Paris local time but the API always writes a +02:00
    offset, even in winter: the offset is replaced, not converted. An end at or
    before the start ("de 21h00 à 00h00") is on the following day.
    """
    occurrences = []
    for chunk in (value or "").split(";"):
        start, _, end = chunk.strip().partition("_")
        try:
            starts_at = _paris_wall_clock(start)
            ends_at = _paris_wall_clock(end) if end else None
            if ends_at and ends_at <= starts_at:
                ends_at += timedelta(days=1)
            occurrences.append(Occurrence(starts_at=starts_at, ends_at=ends_at))
        except (ValueError, ValidationError):
            continue
    return occurrences


def is_evening(occurrences: list[Occurrence]) -> bool | None:
    if not occurrences:
        return None
    for occurrence in occurrences:
        start = occurrence.starts_at.astimezone(PARIS)
        end = (occurrence.ends_at or occurrence.starts_at).astimezone(PARIS)
        if end.date() > start.date() or end.time() >= EVENING_FROM or start.time() >= EVENING_FROM:
            return True
    return False


def parse_offer(payload: dict[str, Any]) -> Offer:
    price_type = (payload.get("price_type") or "").lower()
    is_free = price_type == "gratuit"
    amounts = [] if is_free else sorted(Decimal(a.replace(",", ".")) for a in _EUROS.findall(payload.get("price_detail") or ""))
    booking_url = _safe_url(payload.get("access_link"))
    return Offer(
        label=payload.get("price_type"),
        is_free=is_free,
        price_min=amounts[0] if amounts else None,
        price_max=amounts[-1] if amounts else None,
        booking_url=booking_url,
        online_booking=True if booking_url else None,
    )


def _youth_audience(payload: dict[str, Any]) -> str | None:
    tags = payload.get("qfap_tags") or payload.get("tags") or []
    if isinstance(tags, str):
        tags = tags.split(";")
    if _CHILD_TAGS & {t.strip().lower() for t in tags}:
        return "jeune public"
    audience = payload.get("audience") or ""
    if _CHILD_AUDIENCE.search(audience) and not _ADULT_AUDIENCE.search(audience):
        return "jeune public"
    return None


def _in_window(occurrence: Occurrence, now: datetime, window: timedelta) -> bool:
    return (occurrence.ends_at or occurrence.starts_at) >= now and occurrence.starts_at <= now + window


def _paris_wall_clock(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=PARIS)


def _date(value: str | None) -> date | None:
    return datetime.fromisoformat(value).astimezone(PARIS).date() if value else None


def _safe_url(value: str | None) -> HttpUrl | None:
    try:
        return _url.validate_python(value.strip()) if value else None
    except ValidationError:
        return None


def collect(client: httpx.Client, now: datetime | None = None) -> Iterator[Normalized]:
    now = now or datetime.now(timezone.utc)
    for payload in fetch(client, now.astimezone(PARIS).date()):
        yield normalize(payload, now)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--store",
        choices=["local", "supabase"],
        help="local : data/surprise.db (SQLite) ; supabase : payloads bruts dans raw_records",
    )
    args = parser.parse_args()

    with httpx.Client(timeout=60, follow_redirects=True) as client:
        results = list(collect(client))

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


if __name__ == "__main__":
    main()
