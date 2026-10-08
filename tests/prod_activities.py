"""The activities of the project's base (Supabase, SUPABASE_DB_URL in .env), as evenings are composed from them in
production: read through a connection that refuses any write, and kept FRESH_HOURS in data/tests (reading them takes
some fifteen seconds). Only the activities: the tests' accounts, evenings and caches stay local. The base is built
from them with the code of the moment (parcours.Base.load: filters, tags, originality).

    SURPRISE_PROD_REFRESH=1 uv run pytest     # read them again now
"""

import os
import pickle
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from surprise import parcours
from surprise.local_store import PostgresStore

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "tests" / "activites-prod.pickle"
FRESH_HOURS = 12


def next_friday(today: date | None = None) -> date:
    """The day the app proposes (app/src/lib/dates.ts nextFriday): a Friday is followed by the next one."""
    today = today or date.today()
    return today + timedelta(days=(4 - today.weekday()) % 7 or 7)


def db_url() -> str | None:
    """SUPABASE_DB_URL: from the environment, else from .env (uv run pytest reads no .env)."""
    if url := os.environ.get("SUPABASE_DB_URL"):
        return url
    env = ROOT / ".env"
    if not env.exists():
        return None
    for line in env.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if key.strip() == "SUPABASE_DB_URL" and value.strip():
            return value.strip().strip("\"'")
    return None


class _Rows:
    """What parcours.Base.load reads of a store: the activities and the pages checked."""

    def __init__(self, items: list[dict[str, Any]], checks: dict[str, Any]) -> None:
        self.items, self.checks = items, checks

    def list_for_moderation(self) -> list[dict[str, Any]]:
        return self.items

    def page_checks(self) -> dict[str, Any]:
        return self.checks


def rows() -> _Rows:
    """The activities read from the project's base, at most FRESH_HOURS ago; the last ones kept when it cannot be
    reached. Raises LookupError when there are none to be had."""
    fresh = CACHE.exists() and time.time() - CACHE.stat().st_mtime < FRESH_HOURS * 3600
    if fresh and not os.environ.get("SURPRISE_PROD_REFRESH"):
        return _Rows(*pickle.loads(CACHE.read_bytes()))
    url = db_url()
    try:
        if not url:
            raise LookupError("SUPABASE_DB_URL manque (.env)")
        with PostgresStore(url, read_only=True) as store:
            found = store.list_for_moderation(), store.page_checks()
    except Exception as error:
        if CACHE.exists():
            print(f"Base du projet injoignable ({error}) : activités lues le {time.ctime(CACHE.stat().st_mtime)}")
            return _Rows(*pickle.loads(CACHE.read_bytes()))
        raise LookupError(f"Activités de prod indisponibles : {error}") from error
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    partial = CACHE.with_suffix(".part")
    partial.write_bytes(pickle.dumps(found, protocol=pickle.HIGHEST_PROTOCOL))
    partial.replace(CACHE)  # whole or not at all: another test run may be reading it
    return _Rows(*found)


def base() -> parcours.Base:
    """The activities the evenings are composed from, as the server loads them."""
    return parcours.Base.load(rows())
