"""Clear the activities that are over from the store: their last date gone (or rejected "passé" at collection),
unless an account's history holds them, a step of an evening chosen or a vote. Their raw pages, fiche, moderation,
enrichment, keywords and availability go; a source that still lists one collects it again, rejected "passé".

    uv run --env-file .env python -m surprise.purge           # what would go, by source
    uv run --env-file .env python -m surprise.purge --apply   # deletes it
"""

import argparse
import json
from collections import Counter
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from surprise.collectors.common import split_reasons
from surprise.local_store import LocalStore, open_store

PARIS = ZoneInfo("Europe/Paris")


def last_day(activity: dict[str, Any]) -> date | None:
    """Its last day known: a session's, its run's end (a temporary one's start without it); None for a place always open."""
    days = [datetime.fromisoformat(o["starts_at"]).astimezone(PARIS).date() for o in activity.get("occurrences") or []]
    if end := activity.get("ends_on") or (activity.get("starts_on") if activity.get("kind") == "temporary" else None):
        days.append(date.fromisoformat(end))
    return max(days, default=None)


def is_past(activity: str | None, rejection: str | None, today: date) -> bool:
    if "passé" in split_reasons(rejection):
        return True
    last = last_day(json.loads(activity)) if activity else None
    return last is not None and last < today


def past_activities(store: LocalStore, today: date) -> list[tuple[str, str]]:
    kept = store.kept_activities()
    return [
        (source_id, external_id)
        for source_id, external_id, activity, rejection in store.activities_with_rejection()
        if (source_id, external_id) not in kept and is_past(activity, rejection, today)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Efface les activités passées que nul historique ne garde")
    parser.add_argument("--apply", action="store_true", help="efface pour de bon (sinon, compte seulement)")
    args = parser.parse_args()
    with open_store() as store:
        keys = past_activities(store, datetime.now(PARIS).date())
        for source_id, count in Counter(source_id for source_id, _ in keys).most_common():
            print(f"{source_id} : {count}")
        if args.apply:
            store.delete_activities(keys)
        print(f"{len(keys)} activités passées {'effacées' if args.apply else 'à effacer (--apply pour le faire)'}")


if __name__ == "__main__":
    main()
