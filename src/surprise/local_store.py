"""Local SQLite store, used until Supabase is reachable. Mirrors raw_records."""

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from surprise.models import Activity, RawRecord

DEFAULT_PATH = Path("data/surprise.db")
# "proposed" is the absence of a moderation row: every new activity waits for review.
STATUSES = ("proposed", "approved", "rejected")

SCHEMA = """
create table if not exists raw_records (
  source_id text not null,
  external_id text not null,
  url text,
  payload text not null,
  content_hash text not null,
  fetched_at text not null,
  unique (source_id, external_id, content_hash)
);
create table if not exists normalized (
  source_id text not null,
  external_id text not null,
  content_hash text not null,
  activity text,
  rejection text,
  normalized_at text not null default (datetime('now')),
  primary key (source_id, external_id)
);
-- Separate from normalized, which is replaced on every collection run.
create table if not exists moderation (
  source_id text not null,
  external_id text not null,
  status text not null check (status in ('approved', 'rejected')),
  content_hash text not null,
  decided_at text not null default (datetime('now')),
  primary key (source_id, external_id)
);
-- Image and description found for an activity; also kept across collection runs.
create table if not exists enrichment (
  source_id text not null,
  external_id text not null,
  image_url text,
  image_origin text,
  place_id text,
  site_excerpt text,
  description text,
  description_model text,
  booking_url text,
  latitude real,
  longitude real,
  opening_hours text,
  osm_address text,
  osm_url text,
  enriched_at text not null default (datetime('now')),
  primary key (source_id, external_id)
);
-- Keywords found in the texts of each activity (surprise.keywords), recomputed at will.
create table if not exists keywords (
  source_id text not null,
  external_id text not null,
  keywords text not null,
  computed_at text not null default (datetime('now')),
  primary key (source_id, external_id)
);
-- Couples' answers to the questionnaire (surprise.quiz) and the profile drawn from them.
create table if not exists profiles (
  id text primary key,
  answers text not null,
  profile text not null,
  created_at text not null default (datetime('now'))
);
-- Last answer of the booking engines for a date and a party size (surprise.availability).
create table if not exists availability (
  source_id text not null,
  external_id text not null,
  day text not null,
  party integer not null,
  engine text,
  available integer,
  slots text not null,
  detail text not null,
  checked_at text not null default (datetime('now')),
  primary key (source_id, external_id, day, party)
);
"""


_LATER_COLUMNS = {
    "booking_url": "text", "latitude": "real", "longitude": "real",
    "opening_hours": "text", "osm_address": "text", "osm_url": "text",
}
_ENRICHMENT_COLUMNS = (
    "image_url", "image_origin", "place_id", "site_excerpt", "description", "description_model", "booking_url",
    "latitude", "longitude", "opening_hours", "osm_address", "osm_url",
)


class LocalStore:
    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.executescript(SCHEMA)
        # Columns added after the first databases were created.
        existing = {row[1] for row in self._db.execute("pragma table_info(enrichment)")}
        for column, kind in _LATER_COLUMNS.items():
            if column not in existing:
                self._db.execute(f"alter table enrichment add column {column} {kind}")

    def __enter__(self) -> "LocalStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self._db.close()

    def save_raw_records(self, records: Sequence[RawRecord]) -> int:
        """Insert raw payloads; an unchanged payload (same hash) is skipped. Returns new rows."""
        with self._db:
            before = self._db.total_changes
            self._db.executemany(
                "insert or ignore into raw_records values (?, ?, ?, ?, ?, ?)",
                [
                    (
                        r.source_id,
                        r.external_id,
                        str(r.url) if r.url else None,
                        json.dumps(r.payload, ensure_ascii=False),
                        r.content_hash,
                        r.fetched_at.isoformat(),
                    )
                    for r in records
                ],
            )
            return self._db.total_changes - before

    def save_normalized(self, results: Sequence[tuple[RawRecord, Activity | None, str | None]]) -> None:
        """Keep the latest normalization of each record."""
        with self._db:
            self._db.executemany(
                "insert or replace into normalized (source_id, external_id, content_hash, activity, rejection)"
                " values (?, ?, ?, ?, ?)",
                [
                    (raw.source_id, raw.external_id, raw.content_hash, activity and activity.model_dump_json(), rejection)
                    for raw, activity, rejection in results
                ],
            )

    def list_for_moderation(self) -> list[dict[str, Any]]:
        """Normalized activities with their moderation status and a little source context.

        Activities rejected at collection are "filtered", with their reason, until a moderator decides.
        """
        rows = self._db.execute(
            """
            select n.source_id, n.external_id, n.activity,
                   coalesce(m.status, case when n.rejection is null then 'proposed' else 'filtered' end), n.rejection,
                   m.content_hash is not null and m.content_hash != n.content_hash, m.decided_at,
                   r.url, json_extract(r.payload, '$.lead_text'), json_extract(r.payload, '$.cover_url'),
                   e.image_url, e.image_origin, e.place_id, e.site_excerpt, e.description, e.booking_url,
                   e.opening_hours, e.osm_address, e.osm_url, e.latitude, e.longitude, k.keywords
            from normalized n
            left join moderation m using (source_id, external_id)
            left join enrichment e using (source_id, external_id)
            left join keywords k using (source_id, external_id)
            left join raw_records r
              on r.source_id = n.source_id and r.external_id = n.external_id and r.content_hash = n.content_hash
            where n.activity is not null
            """
        )
        return [
            {
                "source_id": source_id,
                "external_id": external_id,
                "activity": json.loads(activity),
                "status": status,
                "rejection": rejection,
                "changed_since_decision": bool(changed),
                "decided_at": decided_at,
                "source_url": source_url,
                "lead_text": lead_text,
                "cover_url": cover_url,
                "enrichment": {
                    "image_url": image_url,
                    "image_origin": image_origin,
                    "place_id": place_id,
                    "site_excerpt": site_excerpt,
                    "description": description,
                    "booking_url": booking_url,
                    "opening_hours": opening_hours,
                    "osm_address": osm_address,
                    "osm_url": osm_url,
                    "latitude": latitude,
                    "longitude": longitude,
                    "keywords": json.loads(keywords) if keywords is not None else None,  # None: never computed
                },
            }
            for (
                source_id, external_id, activity, status, rejection, changed, decided_at, source_url, lead_text, cover_url,
                image_url, image_origin, place_id, site_excerpt, description, booking_url,
                opening_hours, osm_address, osm_url, latitude, longitude, keywords,
            ) in rows
        ]

    def set_status(self, source_id: str, external_id: str, status: str) -> bool:
        """Record a moderation decision against the current payload. False if the activity is unknown."""
        if status not in STATUSES:
            raise ValueError(f"statut inconnu : {status}")
        with self._db:
            exists = self._db.execute(
                "select 1 from normalized where source_id = ? and external_id = ? and activity is not null",
                (source_id, external_id),
            ).fetchone()
            if not exists:
                return False
            if status == "proposed":
                self._db.execute(
                    "delete from moderation where source_id = ? and external_id = ?", (source_id, external_id)
                )
            else:
                self._db.execute(
                    "insert or replace into moderation (source_id, external_id, status, content_hash)"
                    " select source_id, external_id, ?, content_hash from normalized"
                    " where source_id = ? and external_id = ?",
                    (status, source_id, external_id),
                )
            return True

    def pending_enrichment(self, refresh: bool = False, missing_description: bool = False) -> list[dict[str, Any]]:
        """Kept activities without enrichment (or without description, or all with refresh), with the source's text."""
        rows = self._db.execute(
            """
            select n.source_id, n.external_id, n.activity,
                   json_extract(r.payload, '$.lead_text'), json_extract(r.payload, '$.description')
            from normalized n
            left join raw_records r
              on r.source_id = n.source_id and r.external_id = n.external_id and r.content_hash = n.content_hash
            left join enrichment e using (source_id, external_id)
            left join moderation m using (source_id, external_id)
            -- Activities rejected at collection only once a moderator keeps them.
            where n.activity is not null and (n.rejection is null or m.status = 'approved') and (? or e.source_id is null or (? and e.description is null))
            """,
            (refresh, missing_description),
        )
        return [
            {
                "source_id": source_id,
                "external_id": external_id,
                "activity": json.loads(activity),
                "source_text": "\n".join(filter(None, [lead_text, description])) or None,
            }
            for source_id, external_id, activity, lead_text, description in rows
        ]

    def save_profile(self, profile_id: str, answers: dict[str, Any], profile: dict[str, Any]) -> None:
        with self._db:
            self._db.execute(
                "insert or replace into profiles (id, answers, profile) values (?, ?, ?)",
                (profile_id, json.dumps(answers, ensure_ascii=False), json.dumps(profile, ensure_ascii=False)),
            )

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        row = self._db.execute("select answers, profile, created_at from profiles where id = ?", (profile_id,)).fetchone()
        return row and {"id": profile_id, "answers": json.loads(row[0]), "profile": json.loads(row[1]), "created_at": row[2]}

    def list_profiles(self) -> list[dict[str, Any]]:
        rows = self._db.execute("select id, profile, created_at from profiles order by created_at desc")
        return [{"id": profile_id, "profile": json.loads(profile), "created_at": created_at} for profile_id, profile, created_at in rows]

    def save_keywords(self, keywords: dict[tuple[str, str], str]) -> None:
        """Store each activity's keywords (JSON list), replacing the previous ones."""
        with self._db:
            self._db.executemany(
                "insert or replace into keywords (source_id, external_id, keywords) values (?, ?, ?)",
                [(source_id, external_id, words) for (source_id, external_id), words in keywords.items()],
            )

    def save_enrichment(self, source_id: str, external_id: str, fields: dict[str, str | None]) -> None:
        """Upsert the given fields only: a refresh without descriptions keeps the ones already written."""
        columns = [column for column in _ENRICHMENT_COLUMNS if column in fields]
        updates = ", ".join([f"{column} = excluded.{column}" for column in columns] + ["enriched_at = datetime('now')"])
        with self._db:
            self._db.execute(
                f"insert into enrichment (source_id, external_id{''.join(f', {c}' for c in columns)})"
                f" values (?, ?{', ?' * len(columns)})"
                f" on conflict (source_id, external_id) do update set {updates}",
                (source_id, external_id, *(fields[column] for column in columns)),
            )

    def cached_availability(self, day: str, party: int, max_age_hours: float) -> dict[tuple[str, str], dict[str, Any]]:
        """Availability answers for the date checked less than `max_age_hours` ago; engine None: no supported engine."""
        rows = self._db.execute(
            "select source_id, external_id, engine, available, slots, detail from availability"
            " where day = ? and party = ? and checked_at >= datetime('now', ?)",
            (day, party, f"-{max_age_hours * 3600:.0f} seconds"),
        )
        return {
            (source_id, external_id): {
                "engine": engine,
                "available": None if available is None else bool(available),
                "slots": json.loads(slots),
                "detail": detail,
            }
            for source_id, external_id, engine, available, slots, detail in rows
        }

    def save_availability(
        self, source_id: str, external_id: str, day: str, party: int,
        engine: str | None, available: bool | None, slots: list[str], detail: str,
    ) -> None:
        with self._db:
            self._db.execute(
                "insert or replace into availability (source_id, external_id, day, party, engine, available, slots, detail)"
                " values (?, ?, ?, ?, ?, ?, ?, ?)",
                (source_id, external_id, day, party, engine, available, json.dumps(slots), detail),
            )
