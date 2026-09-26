"""Collector for Que Faire à Paris (Ville de Paris open data, ODbL).

API: Opendatasoft Explore v2.1, dataset ``que-faire-a-paris-``.
The export endpoint returns every matching record in one call (the records
endpoint caps offset + limit at 10 000). ``OPENDATA_PARIS_URL`` overrides the
portal, e.g. the Opendatasoft mirror https://parisdata.opendatasoft.com when
opendata.paris.fr does not resolve.
"""

import os
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterator
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from surprise.collectors.common import Normalized, euro_amounts, run, safe_url
from surprise.categories import categorize
from surprise.models import OUT_OF_AREA, Activity, ActivityKind, Image, Occurrence, Offer, RawRecord, Venue

SOURCE_ID = "que_faire_a_paris"
DATASET = "que-faire-a-paris-"
DEFAULT_BASE_URL = "https://opendata.paris.fr"
PARIS = ZoneInfo("Europe/Paris")
WINDOW = timedelta(weeks=6)
# An occurrence counts as an evening one if it is still running at this hour.
EVENING_FROM = time(19, 0)

_CHILD_AUDIENCE = re.compile(r"enfant|jeune public|famille|b[ée]b[ée]", re.IGNORECASE)
_ADULT_AUDIENCE = re.compile(r"adulte", re.IGNORECASE)
_CHILD_TAGS = {"enfants", "jeune public", "famille"}
# Not couple outings: municipal sport programmes, senior, health and social events.
_OFF_TARGET_TAGS = {"sport", "santé", "solidarité", "senior", "handicap", "prévention"}
_NEUTRAL_TAGS = {"loisirs"}
_OFF_TARGET_TITLE = re.compile(
    r"\bparis sportives?\b|\bparis sport\b|\bgymnase\b|\bcentre sportif\b|\bsport seniors?\b", re.IGNORECASE
)


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
        url=safe_url(payload.get("url")),
        payload=payload,
    )


def normalize(payload: dict[str, Any], now: datetime, window: timedelta = WINDOW) -> Normalized:
    raw = to_raw_record(payload)

    if reason := _youth_audience(payload) or _off_target(payload):
        return Normalized(raw, rejection=reason)

    try:
        venue = Venue(
            name=payload.get("address_name") or payload.get("contact_organisation_name") or "Lieu inconnu",
            address=payload.get("address_street"),
            postal_code=str(payload.get("address_zipcode") or ""),
            latitude=(payload.get("lat_lon") or {}).get("lat"),
            longitude=(payload.get("lat_lon") or {}).get("lon"),
            website=safe_url(payload.get("address_url")),
        )
    except ValidationError:
        return Normalized(raw, rejection=OUT_OF_AREA)

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
            website=safe_url(payload.get("contact_url")) or safe_url(payload.get("url")),
            is_evening=is_evening(occurrences),
            venue=venue,
            categories=categorize(payload["title"], venue.name, tags=_tags(payload)),
            image=parse_image(payload),
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
    amounts = [] if is_free else euro_amounts(payload.get("price_detail"))
    booking_url = safe_url(payload.get("access_link"))
    return Offer(
        label=payload.get("price_type"),
        is_free=is_free,
        price_min=amounts[0] if amounts else None,
        price_max=amounts[-1] if amounts else None,
        booking_url=booking_url,
        online_booking=True if booking_url else None,
    )


def parse_image(payload: dict[str, Any]) -> Image | None:
    if not (url := safe_url(payload.get("cover_url"))):
        return None
    credit = (payload.get("cover_credit") or "").strip()
    return Image(
        url=url,
        license=f"Que Faire à Paris — crédit : {credit}" if credit else "Que Faire à Paris — crédit non précisé",
        source_url=safe_url(payload.get("url")),
    )


def _youth_audience(payload: dict[str, Any]) -> str | None:
    if _CHILD_TAGS & {t.strip().lower() for t in _tags(payload)}:
        return "jeune public"
    audience = payload.get("audience") or ""
    if _CHILD_AUDIENCE.search(audience) and not _ADULT_AUDIENCE.search(audience):
        return "jeune public"
    return None


def _off_target(payload: dict[str, Any]) -> str | None:
    """Tagged only with off-target themes (a dance night tagged Sport;Danse stays), or a sports venue."""
    tags = {t.strip().lower() for t in _tags(payload)} - {""}
    if tags & _OFF_TARGET_TAGS and tags <= _OFF_TARGET_TAGS | _NEUTRAL_TAGS:
        return "hors cible"
    if _OFF_TARGET_TITLE.search(payload.get("title") or "") or _OFF_TARGET_TITLE.search(payload.get("address_name") or ""):
        return "hors cible"
    return None


def _tags(payload: dict[str, Any]) -> list[str]:
    tags = payload.get("qfap_tags") or payload.get("tags") or []
    return tags.split(";") if isinstance(tags, str) else tags


def _in_window(occurrence: Occurrence, now: datetime, window: timedelta) -> bool:
    return (occurrence.ends_at or occurrence.starts_at) >= now and occurrence.starts_at <= now + window


def _paris_wall_clock(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=PARIS)


def _date(value: str | None) -> date | None:
    return datetime.fromisoformat(value).astimezone(PARIS).date() if value else None


def collect(client: httpx.Client, now: datetime | None = None) -> Iterator[Normalized]:
    now = now or datetime.now(timezone.utc)
    for payload in fetch(client, now.astimezone(PARIS).date()):
        yield normalize(payload, now)


def main() -> None:
    run(__doc__.splitlines()[0], lambda: _collect_with_client())


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
