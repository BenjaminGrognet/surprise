"""The pipeline's store: a SQLite file, or the same tables in Supabase Postgres (schema pipeline).

The SQL is written once for both. `open_store()` picks Supabase when SUPABASE_DB_URL is set;
`python -m surprise.local_store` copies the SQLite file to Supabase.
"""

import argparse
import json
import os
import sqlite3
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
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
-- What a booking link or official site says (surprise.booking.page_verdict), read again after a month.
create table if not exists page_checks (
  url text primary key,
  engine text,
  closed boolean not null,
  checked_at text not null default (datetime('now'))
);
-- OpenStreetMap place of each venue (surprise.enrich), place null when none was found; asked again after 3 months.
create table if not exists osm_places (
  name text not null,
  postal_code text not null,
  place text,
  checked_at text not null default (datetime('now')),
  primary key (name, postal_code)
);
-- Every profile the questionnaire draws (surprise.quiz), with its answers.
create table if not exists profiles (
  id text primary key,
  answers text not null,
  profile text not null,
  created_at text not null default (datetime('now'))
);
-- A composed evening (surprise.parcours): the evenings asked, its routes, their steps (see the Supabase migration).
create table if not exists soirees (
  id text primary key,
  requests text not null,
  naming integer not null default 0,
  created_at text not null default (datetime('now')),
  saved_at text not null default (datetime('now'))
);
create table if not exists soiree_routes (
  soiree_id text not null references soirees (id) on delete cascade,
  route integer not null,
  request integer,
  title text not null,
  pitch text not null,
  score real not null,
  primary key (soiree_id, route)
);
-- A redraw keeps the steps it replaces (replaced_at).
create table if not exists soiree_steps (
  id integer primary key autoincrement,
  soiree_id text not null references soirees (id) on delete cascade,
  route integer not null,
  position integer not null,
  source_id text not null,
  external_id text not null,
  starts_at text not null,
  ends_at text not null,
  night boolean not null default false,
  step text not null,
  created_at text not null default (datetime('now')),
  replaced_at text
);
create unique index if not exists soiree_steps_current_idx on soiree_steps (soiree_id, route, position) where replaced_at is null;
"""
# A page read less than this long ago is not read again: its stored payloads are normalized anew.
FRESH_DAYS = 7
PAGE_CHECK_DAYS = 30
OSM_PLACE_DAYS = 90


_LATER_COLUMNS = {
    "booking_url": "text", "latitude": "real", "longitude": "real",
    "opening_hours": "text", "osm_address": "text", "osm_url": "text",
}
_ENRICHMENT_COLUMNS = (
    "image_url", "image_origin", "place_id", "site_excerpt", "description", "description_model", "booking_url",
    "latitude", "longitude", "opening_hours", "osm_address", "osm_url",
)


def _partial(title: str) -> dict[str, Any]:
    """What moderation shows of a record rejected before its fiche was built: its title."""
    return {"title": title, "venue": {}, "categories": [], "occurrences": [], "offers": []}


def _no_nul(text: str | None) -> str | None:
    # Postgres jsonb refuses the NUL character, which a few scraped pages carry.
    return text.replace("\\u0000", "") if text else text


class LocalStore:
    """SQLite file; PostgresStore runs the same statements on Supabase."""

    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
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

    def _run(self, sql: str, params: Sequence[Any] = ()) -> Any:
        return self._db.execute(sql, params)

    def _run_many(self, sql: str, rows: Sequence[Sequence[Any]]) -> int:
        cursor = self._db.cursor()
        cursor.executemany(sql, rows)
        return cursor.rowcount

    def _transaction(self) -> Any:
        return self._db

    def version(self) -> Any:
        """Changes whenever the data does: the moderation list is cached on it."""
        return self._path.stat().st_mtime_ns

    def save_raw_records(self, records: Sequence[RawRecord]) -> int:
        """Insert raw payloads; an unchanged payload (same hash) only gets its new fetch time. Returns rows written."""
        with self._transaction():
            return self._run_many(
                "insert into raw_records (source_id, external_id, url, payload, content_hash, fetched_at)"
                " values (?, ?, ?, ?, ?, ?) on conflict (source_id, external_id, content_hash)"
                " do update set fetched_at = excluded.fetched_at, payload = excluded.payload",
                [
                    (
                        r.source_id,
                        r.external_id,
                        str(r.url) if r.url else None,
                        _no_nul(json.dumps(r.payload, ensure_ascii=False)),
                        r.content_hash,
                        r.fetched_at.isoformat(),
                    )
                    for r in records
                ],
            )

    def save_normalized(self, results: Sequence[tuple[RawRecord, Activity | None, str | None]]) -> None:
        """Keep the latest normalization of each record."""
        with self._transaction():
            self._run_many(
                "insert into normalized (source_id, external_id, content_hash, activity, rejection)"
                " values (?, ?, ?, ?, ?)"
                " on conflict (source_id, external_id) do update set content_hash = excluded.content_hash,"
                " activity = excluded.activity, rejection = excluded.rejection, normalized_at = current_timestamp",
                [
                    (raw.source_id, raw.external_id, raw.content_hash, activity and _no_nul(activity.model_dump_json()), rejection)
                    for raw, activity, rejection in results
                ],
            )

    def raw_with_rejection(self) -> list[tuple[str, str, str | None]]:
        """Every raw payload (source, JSON text) with its current rejection, to normalize again."""
        return self._run(
            "select r.source_id, r.payload, n.rejection from raw_records r left join normalized n using (source_id, external_id)"
        ).fetchall()

    def fresh_pages(self, source_id: str, days: float = FRESH_DAYS) -> dict[str, list[dict[str, Any]]]:
        """Payloads of the source's pages read less than `days` ago, by page ("_page"): not to be read again."""
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = self._run(
            "select r.payload ->> '_page', r.payload from raw_records r join normalized n"
            " on n.source_id = r.source_id and n.external_id = r.external_id and n.content_hash = r.content_hash"
            " where r.source_id = ? and r.fetched_at >= ? and r.payload ->> '_page' is not null",
            (source_id, since),
        )
        pages: dict[str, list[dict[str, Any]]] = {}
        for page, payload in rows:
            pages.setdefault(page, []).append(json.loads(payload) | {"_cached": True})
        return pages

    def page_checks(self, days: float = PAGE_CHECK_DAYS) -> dict[str, tuple[str | None, bool]]:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        rows = self._run("select url, engine, closed from page_checks where checked_at >= ?", (since,))
        return {url: (engine, bool(closed)) for url, engine, closed in rows}

    def save_page_checks(self, verdicts: dict[str, tuple[str | None, bool]]) -> None:
        with self._transaction():
            self._run_many(
                "insert into page_checks (url, engine, closed) values (?, ?, ?)"
                " on conflict (url) do update set engine = excluded.engine, closed = excluded.closed,"
                " checked_at = current_timestamp",
                [(url, engine, closed) for url, (engine, closed) in verdicts.items()],
            )

    def osm_places(self, days: float = OSM_PLACE_DAYS) -> dict[tuple[str, str], dict[str, Any] | None]:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        rows = self._run("select name, postal_code, place from osm_places where checked_at >= ?", (since,))
        return {(name, postal_code): json.loads(place) if place else None for name, postal_code, place in rows}

    def save_osm_places(self, places: dict[tuple[str, str], dict[str, Any] | None]) -> None:
        with self._transaction():
            self._run_many(
                "insert into osm_places (name, postal_code, place) values (?, ?, ?)"
                " on conflict (name, postal_code) do update set place = excluded.place, checked_at = current_timestamp",
                [(name, postal_code, place and json.dumps(place)) for (name, postal_code), place in places.items()],
            )

    def save_profile(self, profile_id: str, answers: dict[str, Any], profile: dict[str, Any]) -> None:
        with self._transaction():
            self._run(
                "insert into profiles (id, answers, profile) values (?, ?, ?)",
                (profile_id, json.dumps(answers, ensure_ascii=False), json.dumps(profile, ensure_ascii=False)),
            )

    def soiree(self, soiree_id: str) -> dict[str, Any] | None:
        """An evening as saved: its requests (JSON), naming, routes, current steps, every activity it ever showed, and
        each route's number of steps as composed."""
        row = self._run("select requests, naming from soirees where id = ?", (soiree_id,)).fetchone()
        if row is None:
            return None
        return {
            "requests": row[0],
            "naming": row[1],
            "routes": self._run(
                "select route, request, title, pitch, score from soiree_routes where soiree_id = ? order by route", (soiree_id,)
            ).fetchall(),
            "steps": self._run(
                "select route, night, step from soiree_steps where soiree_id = ? and replaced_at is null order by route, position",
                (soiree_id,),
            ).fetchall(),
            "seen": self._run(
                "select distinct source_id, external_id from soiree_steps where soiree_id = ? and not night", (soiree_id,)
            ).fetchall(),
            # Each route's steps as composed, before the couple took some out: its highest position ever saved.
            "sizes": dict(self._run(
                "select route, max(position) + 1 from soiree_steps where soiree_id = ? and not night group by route", (soiree_id,)
            ).fetchall()),
        }

    def chosen_activities(self, routes: Sequence[tuple[str, int]]) -> set[tuple[str, str]]:
        """The activities of these routes (evening, route index), as they were when chosen: their current steps."""
        found: set[tuple[str, str]] = set()
        for soiree_id, route in routes:
            found |= set(self._run(
                "select source_id, external_id from soiree_steps where soiree_id = ? and route = ? and not night and replaced_at is null",
                (soiree_id, route),
            ).fetchall())
        return found

    def save_soiree(
        self, soiree_id: str, requests: str, naming: int, routes: Sequence[tuple[Any, ...]], steps: Sequence[tuple[Any, ...]]
    ) -> None:
        """The evening, its routes (route, request, title, pitch, score) and steps (route, position, source_id,
        external_id, starts_at, ends_at, night, step JSON). A step whose activity changed is kept, marked replaced."""
        with self._transaction():
            self._run(
                "insert into soirees (id, requests, naming) values (?, ?, ?) on conflict (id) do update"
                " set requests = excluded.requests, naming = excluded.naming, saved_at = current_timestamp",
                (soiree_id, requests, naming),
            )
            self._run("delete from soiree_routes where soiree_id = ?", (soiree_id,))
            self._run_many(
                "insert into soiree_routes (soiree_id, route, request, title, pitch, score) values (?, ?, ?, ?, ?, ?)",
                [(soiree_id, *route) for route in routes],
            )
            current = {
                (route, position, source_id, external_id, bool(night)): step_id
                for step_id, route, position, source_id, external_id, night in self._run(
                    "select id, route, position, source_id, external_id, night from soiree_steps"
                    " where soiree_id = ? and replaced_at is null",
                    (soiree_id,),
                ).fetchall()
            }
            new = {(*step[:4], step[6]): step for step in steps}
            self._run_many(
                "update soiree_steps set replaced_at = current_timestamp where id = ?",
                [(step_id,) for key, step_id in current.items() if key not in new],
            )
            # The same activity at the same place is not replaced: only its hours may have moved (a bar shortened).
            self._run_many(
                "update soiree_steps set starts_at = ?, ends_at = ?, step = ? where id = ?",
                [(step[4], step[5], step[7], current[key]) for key, step in new.items() if key in current],
            )
            self._run_many(
                "insert into soiree_steps (soiree_id, route, position, source_id, external_id, starts_at, ends_at, night, step)"
                " values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(soiree_id, *step) for key, step in new.items() if key not in current],
            )

    def list_for_moderation(self) -> list[dict[str, Any]]:
        """Normalized activities with their moderation status and a little source context.

        Activities rejected at collection are "filtered", with their reasons, until a moderator decides. Those rejected
        before their fiche could be built (no place, out of the area…) are listed too, "partial": their title and page only.
        """
        rows = self._run(
            """
            select n.source_id, n.external_id, n.activity,
                   case when n.activity is null then 'filtered'
                        else coalesce(m.status, case when n.rejection is null then 'proposed' else 'filtered' end) end,
                   n.rejection,
                   m.content_hash is not null and m.content_hash != n.content_hash, cast(m.decided_at as text),
                   r.url, r.payload ->> 'lead_text', r.payload ->> 'cover_url',
                   e.image_url, e.image_origin, e.place_id, e.site_excerpt, e.description, e.booking_url,
                   e.opening_hours, e.osm_address, e.osm_url, e.latitude, e.longitude, k.keywords,
                   coalesce(r.payload ->> 'title', r.payload ->> 'name')
            from normalized n
            left join moderation m using (source_id, external_id)
            left join enrichment e using (source_id, external_id)
            left join keywords k using (source_id, external_id)
            left join raw_records r
              on r.source_id = n.source_id and r.external_id = n.external_id and r.content_hash = n.content_hash
            """
        )
        return [
            {
                "source_id": source_id,
                "external_id": external_id,
                "activity": json.loads(activity) if activity else _partial(title or source_url or external_id),
                "partial": activity is None,
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
                opening_hours, osm_address, osm_url, latitude, longitude, keywords, title,
            ) in rows
        ]

    def set_status(self, source_id: str, external_id: str, status: str) -> bool:
        """Record a moderation decision against the current payload. False if the activity is unknown."""
        if status not in STATUSES:
            raise ValueError(f"statut inconnu : {status}")
        with self._transaction():
            exists = self._run(
                "select 1 from normalized where source_id = ? and external_id = ? and activity is not null",
                (source_id, external_id),
            ).fetchone()
            if not exists:
                return False
            if status == "proposed":
                self._run("delete from moderation where source_id = ? and external_id = ?", (source_id, external_id))
            else:
                self._run(
                    "insert into moderation (source_id, external_id, status, content_hash)"
                    " select source_id, external_id, cast(? as text), content_hash from normalized"
                    " where source_id = ? and external_id = ?"
                    " on conflict (source_id, external_id) do update set status = excluded.status,"
                    " content_hash = excluded.content_hash, decided_at = current_timestamp",
                    (status, source_id, external_id),
                )
            return True

    def pending_enrichment(self, refresh: bool = False, missing_description: bool = False) -> list[dict[str, Any]]:
        """Kept activities without enrichment (or without description, or all with refresh), with the source's text.

        "enriched": already enriched once, with the official site's excerpt found then.
        """
        rows = self._run(
            """
            select n.source_id, n.external_id, n.activity,
                   r.payload ->> 'lead_text', r.payload ->> 'description', e.source_id is not null, e.site_excerpt
            from normalized n
            left join enrichment e using (source_id, external_id)
            left join moderation m using (source_id, external_id)
            left join raw_records r
              on r.source_id = n.source_id and r.external_id = n.external_id and r.content_hash = n.content_hash
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
                "enriched": bool(enriched),
                "site_excerpt": site_excerpt,
            }
            for source_id, external_id, activity, lead_text, description, enriched, site_excerpt in rows
        ]

    def save_keywords(self, keywords: dict[tuple[str, str], str]) -> None:
        """Store each activity's keywords (JSON list), replacing the previous ones."""
        with self._transaction():
            self._run_many(
                "insert into keywords (source_id, external_id, keywords) values (?, ?, ?)"
                " on conflict (source_id, external_id) do update set keywords = excluded.keywords,"
                " computed_at = current_timestamp",
                [(source_id, external_id, words) for (source_id, external_id), words in keywords.items()],
            )

    def save_enrichment(self, source_id: str, external_id: str, fields: dict[str, str | None]) -> None:
        """Upsert the given fields only: a refresh without descriptions keeps the ones already written."""
        columns = [column for column in _ENRICHMENT_COLUMNS if column in fields]
        updates = ", ".join([f"{column} = excluded.{column}" for column in columns] + ["enriched_at = current_timestamp"])
        with self._transaction():
            self._run(
                f"insert into enrichment (source_id, external_id{''.join(f', {c}' for c in columns)})"
                f" values (?, ?{', ?' * len(columns)})"
                f" on conflict (source_id, external_id) do update set {updates}",
                (source_id, external_id, *(fields[column] for column in columns)),
            )

    def cached_availability(self, day: str, party: int, max_age_hours: float) -> dict[tuple[str, str], dict[str, Any]]:
        """Availability answers for the date checked less than `max_age_hours` ago; engine None: no supported engine."""
        since = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).strftime("%Y-%m-%d %H:%M:%S")
        rows = self._run(
            "select source_id, external_id, engine, available, slots, detail from availability"
            " where day = ? and party = ? and checked_at >= ?",
            (day, party, since),
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
        with self._transaction():
            self._run(
                "insert into availability (source_id, external_id, day, party, engine, available, slots, detail)"
                " values (?, ?, ?, ?, ?, ?, ?, ?)"
                " on conflict (source_id, external_id, day, party) do update set engine = excluded.engine,"
                " available = excluded.available, slots = excluded.slots, detail = excluded.detail,"
                " checked_at = current_timestamp",
                (source_id, external_id, day, party, engine, available, json.dumps(slots), detail),
            )


class PostgresStore(LocalStore):
    """The same tables in Supabase: schema pipeline, raw_records in public (SUPABASE_DB_URL)."""

    def __init__(self, url: str) -> None:
        import psycopg
        from psycopg.types.string import TextLoader

        self._db = psycopg.connect(url, autocommit=True)
        # JSON columns read back as text, like SQLite's.
        for kind in ("json", "jsonb"):
            self._db.adapters.register_loader(kind, TextLoader)
        self._db.execute("set search_path = pipeline, public")
        self._db.execute("set timezone = 'UTC'")

    def _run(self, sql: str, params: Sequence[Any] = ()) -> Any:
        return self._db.execute(sql.replace("?", "%s"), params)

    def _run_many(self, sql: str, rows: Sequence[Sequence[Any]]) -> int:
        with self._db.cursor() as cursor:
            cursor.executemany(sql.replace("?", "%s"), rows)
            return cursor.rowcount

    def _transaction(self) -> Any:
        return self._db.transaction()

    def version(self) -> Any:
        return self._run(
            "select (select max(normalized_at) from normalized), (select max(decided_at) from moderation),"
            " (select max(enriched_at) from enrichment), (select max(computed_at) from keywords)"
        ).fetchone()


def open_store(db: Path | str | None = None) -> LocalStore:
    """`db` (a SQLite path or a postgresql:// URL), else SUPABASE_DB_URL when set, else data/surprise.db."""
    db = db or os.environ.get("SUPABASE_DB_URL") or DEFAULT_PATH
    if str(db).startswith(("postgres://", "postgresql://")):
        return PostgresStore(str(db))
    return LocalStore(Path(db))


# Copied to Supabase; availability is a 6-hour cache, left behind.
_COPIED = {
    "raw_records": ("source_id", "external_id", "url", "payload", "content_hash", "fetched_at"),
    "normalized": ("source_id", "external_id", "content_hash", "activity", "rejection", "normalized_at"),
    "moderation": ("source_id", "external_id", "status", "content_hash", "decided_at"),
    "enrichment": ("source_id", "external_id", *_ENRICHMENT_COLUMNS, "enriched_at"),
    "keywords": ("source_id", "external_id", "keywords", "computed_at"),
    "osm_places": ("name", "postal_code", "place", "checked_at"),
    "profiles": ("id", "answers", "profile", "created_at"),
    "soirees": ("id", "requests", "naming", "created_at", "saved_at"),
    "soiree_routes": ("soiree_id", "route", "request", "title", "pitch", "score"),
    # ponytail: without its id, a replaced step is copied again on every run; key the history if copies get repeated.
    "soiree_steps": (
        "soiree_id", "route", "position", "source_id", "external_id", "starts_at", "ends_at", "night", "step", "created_at", "replaced_at",
    ),
}


def copy(source: LocalStore, target: LocalStore) -> dict[str, int]:
    """Rows of `source` missing from `target`, table by table; the count added to each."""
    added = {}
    for table, columns in _COPIED.items():
        rows = [[_no_nul(v) if isinstance(v, str) else v for v in row] for row in source._run(f"select {', '.join(columns)} from {table}")]
        with target._transaction():
            added[table] = target._run_many(
                f"insert into {table} ({', '.join(columns)}) values ({', '.join('?' * len(columns))}) on conflict do nothing", rows
            )
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description="Copie la base SQLite vers Supabase (SUPABASE_DB_URL)")
    parser.add_argument("--db", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    with LocalStore(args.db) as source, PostgresStore(os.environ["SUPABASE_DB_URL"]) as target:
        for table, count in copy(source, target).items():
            print(f"{table} : {count} lignes ajoutées")


if __name__ == "__main__":
    main()
