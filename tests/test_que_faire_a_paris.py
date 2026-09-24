import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import respx

from surprise.collectors import que_faire_a_paris as qfap
from surprise.store import SupabaseStore

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "que_faire_a_paris.json").read_text())
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
    assert by_id("3").rejection == "hors Paris intra-muros"


def test_daytime_free_event_with_invalid_url():
    result = by_id("4")
    assert result.raw.url is None
    assert result.activity.venue.arrondissement == 16
    assert result.activity.is_evening is False
    assert result.activity.offers[0].is_free is True


def test_is_evening_unknown_without_occurrences():
    assert qfap.is_evening([]) is None


@respx.mock
def test_collect_queries_the_six_week_window():
    route = respx.get(qfap.EXPORT_URL).mock(return_value=httpx.Response(200, json=FIXTURE))
    with httpx.Client() as client:
        results = list(qfap.collect(client, NOW))
    assert route.calls.last.request.url.params["where"] == (
        "date_end >= date'2026-09-25' and date_start <= date'2026-11-06'"
    )
    assert [r.rejection for r in results] == [None, "jeune public", "hors Paris intra-muros", None]


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
