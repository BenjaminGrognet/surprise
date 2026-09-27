"""Supabase persistence through PostgREST, using the service role key (bypasses RLS)."""

import os
from collections.abc import Sequence

import httpx

from surprise.models import RawRecord

BATCH_SIZE = 500


class SupabaseStore:
    def __init__(self, url: str, service_key: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=60)
        self._rest = f"{url.rstrip('/')}/rest/v1"
        self._headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}

    @classmethod
    def from_env(cls) -> "SupabaseStore":
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SECRET_KEY"]
        return cls(os.environ["SUPABASE_URL"], key)

    def __enter__(self) -> "SupabaseStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self._client.close()

    def save_raw_records(self, records: Sequence[RawRecord]) -> int:
        """Insert raw payloads; an unchanged payload (same hash) is skipped."""
        for start in range(0, len(records), BATCH_SIZE):
            batch = records[start : start + BATCH_SIZE]
            response = self._client.post(
                f"{self._rest}/raw_records",
                params={"on_conflict": "source_id,external_id,content_hash"},
                headers={**self._headers, "Prefer": "resolution=ignore-duplicates,return=minimal"},
                json=[r.model_dump(mode="json") for r in batch],
            )
            response.raise_for_status()
        return len(records)
