import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import respx

from surprise.collectors import que_faire_a_paris as qfap
from surprise.store import SupabaseStore

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "que_faire_a_paris.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 9, 24, 22, tzinfo=timezone.utc)


def by_id(external_id):
    return qfap.normalize(next(p for p in FIXTURE if p["id"] == external_id), NOW)


def test_event_is_normalized():
    result = by_id("12345")
    activity = result.activity
    assert result.rejection is None
    assert result.raw.external_id == "12345"
    assert activity.title == "Concert à la bougie dans une église"
    assert activity.description is None
    assert activity.venue.arrondissement == 5
    assert activity.venue.latitude == 48.8521
    assert str(activity.website) == "https://example.com/concert"
    assert activity.is_evening is True


def test_occurrences_are_limited_to_the_window():
    starts = [o.starts_at.isoformat() for o in by_id("12345").activity.occurrences]
    assert starts == ["2026-10-01T20:00:00+02:00", "2026-10-02T20:00:00+02:00"]


def test_offer_prices_and_booking():
    offer = by_id("12345").activity.offers[0]
    assert (offer.is_free, offer.price_min, offer.price_max) == (False, Decimal("25"), Decimal("45.50"))
    assert str(offer.booking_url) == "https://example.com/billetterie"
    assert offer.online_booking is True


def test_youth_events_are_rejected():
    assert by_id("2").rejection == "jeune public"


def test_events_outside_paris_are_rejected():
    assert by_id("3").rejection == "hors Paris et proche banlieue"


def test_daytime_free_event_with_invalid_url():
    result = by_id("4")
    assert result.raw.url is None
    assert result.activity.venue.arrondissement == 16
    assert result.activity.is_evening is False
    assert result.activity.offers[0].is_free is True


def test_is_evening_unknown_without_occurrences():
    assert qfap.is_evening([]) is None


@respx.mock
def test_collect_queries_the_six_week_window(monkeypatch):
    monkeypatch.delenv("OPENDATA_PARIS_URL", raising=False)
    route = respx.get(
        "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/que-faire-a-paris-/exports/json"
    ).mock(return_value=httpx.Response(200, json=FIXTURE))
    with httpx.Client() as client:
        results = list(qfap.collect(client, NOW))
    assert route.calls.last.request.url.params["where"] == (
        "date_end >= date'2026-09-25' and date_start <= date'2026-11-06'"
    )
    assert [r.rejection for r in results] == [None, "jeune public", "hors Paris et proche banlieue", None]


def test_portal_url_can_be_overridden(monkeypatch):
    monkeypatch.setenv("OPENDATA_PARIS_URL", "https://parisdata.opendatasoft.com/")
    assert qfap.export_url() == (
        "https://parisdata.opendatasoft.com/api/explore/v2.1/catalog/datasets/que-faire-a-paris-/exports/json"
    )


@respx.mock
def test_store_skips_duplicate_raw_records():
    route = respx.post("https://db.example.com/rest/v1/raw_records").mock(return_value=httpx.Response(201))
    records = [qfap.to_raw_record(p) for p in FIXTURE]
    with SupabaseStore("https://db.example.com/", "service-key") as store:
        assert store.save_raw_records(records) == 4
    request = route.calls.last.request
    assert request.url.params["on_conflict"] == "source_id,external_id,content_hash"
    assert "resolution=ignore-duplicates" in request.headers["Prefer"]
    assert json.loads(request.content)[0]["source_id"] == "que_faire_a_paris"


def test_occurrence_offset_is_ignored_in_winter():
    # The API writes +02:00 all year; "de 20h00 à 22h00" is 20:00 Paris time.
    [occurrence] = qfap.parse_occurrences("2026-11-02T20:00:00+02:00_2026-11-02T22:00:00+02:00")
    assert occurrence.starts_at.isoformat() == "2026-11-02T20:00:00+01:00"
    assert occurrence.ends_at.isoformat() == "2026-11-02T22:00:00+01:00"


def test_dates_come_from_occurrences_not_shifted_fields():
    payload = next(p for p in FIXTURE if p["id"] == "12345") | {
        "date_start": "2026-09-27T00:00:00+02:00",
        "date_end": "2026-10-03T01:30:00+02:00",
        "occurrences": "2026-09-26T21:00:00+02:00_2026-09-26T22:15:00+02:00;"
        "2026-10-02T20:45:00+02:00_2026-10-02T22:00:00+02:00",
    }
    activity = qfap.normalize(payload, NOW).activity
    assert (activity.starts_on.isoformat(), activity.ends_on.isoformat()) == ("2026-09-26", "2026-10-02")


def test_occurrence_ending_at_midnight_ends_the_next_day():
    [occurrence] = qfap.parse_occurrences("2026-09-30T21:00:00+02:00_2026-09-30T00:00:00+02:00")
    assert occurrence.ends_at.isoformat() == "2026-10-01T00:00:00+02:00"


def test_off_target_events_are_rejected():
    base = next(p for p in FIXTURE if p["id"] == "12345")
    assert qfap.normalize(base | {"qfap_tags": "Sport;Loisirs"}, NOW).rejection == "hors cible"
    assert qfap.normalize(base | {"qfap_tags": "Solidarité"}, NOW).rejection == "hors cible"
    assert qfap.normalize(base | {"title": "Paris sport proximité : badminton"}, NOW).rejection == "hors cible"
    assert qfap.normalize(base | {"address_name": "Gymnase Auguste Blanqui"}, NOW).rejection == "hors cible"
    # A dance night also tagged Sport is a real outing.
    assert qfap.normalize(base | {"qfap_tags": "Danse;Loisirs;Sport"}, NOW).rejection is None
