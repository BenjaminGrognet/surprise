"""Local SQLite store, used until Supabase is reachable. Mirrors raw_records."""

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path

from surprise.models import Activity, RawRecord

DEFAULT_PATH = Path("data/surprise.db")

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
"""


class LocalStore:
    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.executescript(SCHEMA)

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
