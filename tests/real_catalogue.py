"""Real activities of the base (tests/fixtures/catalogue.json, written by tests/snapshot_catalogue.py), as the
evenings are composed from: their sessions moved to the day asked, a whole number of weeks on, so that opening
hours by weekday still hold."""

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from surprise import parcours

PATH = Path(__file__).parent / "fixtures" / "catalogue.json"


def _moved(value: str | None, shift: timedelta) -> str | None:
    if not value:
        return value
    if len(value) == 10:
        return (date.fromisoformat(value) + shift).isoformat()
    return (datetime.fromisoformat(value) + shift).isoformat()


def items(day: date | None = None) -> list[dict[str, Any]]:
    """The activities, their dates moved from the snapshot's day to `day` (the same weekday)."""
    data = json.loads(PATH.read_text(encoding="utf-8"))
    shift = (day or date.fromisoformat(data["day"])) - date.fromisoformat(data["day"])
    assert shift.days % 7 == 0, f"{day} n'est pas un {['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche'][date.fromisoformat(data['day']).weekday()]}"
    for item in data["items"]:
        activity = item["activity"]
        for field in ("starts_on", "ends_on"):
            activity[field] = _moved(activity.get(field), shift)
        for occurrence in activity.get("occurrences") or []:
            for field in ("starts_at", "ends_at"):
                occurrence[field] = _moved(occurrence.get(field), shift)
    return data["items"]


def base(day: date | None = None) -> parcours.Base:
    """The Base the API composes from, with the originality the whole base gave each activity."""
    found = items(day)
    return parcours.Base(found, {(i["source_id"], i["external_id"]): i["originality"] for i in found})
