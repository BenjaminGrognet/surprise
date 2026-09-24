from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from surprise.models import Activity, ActivityKind, Occurrence, Offer, RawRecord, Venue


@pytest.mark.parametrize("postal_code, arrondissement", [("75001", 1), ("75020", 20), ("75116", 16)])
def test_paris_venue(postal_code, arrondissement):
    assert Venue(name="Lieu", postal_code=postal_code).arrondissement == arrondissement


@pytest.mark.parametrize("postal_code", ["75000", "75021", "93100", "92120"])
def test_venue_outside_paris_is_rejected(postal_code):
    with pytest.raises(ValidationError):
        Venue(name="Lieu", postal_code=postal_code)


def test_offer_price_consistency():
    with pytest.raises(ValidationError):
        Offer(price_min=30, price_max=10)
    with pytest.raises(ValidationError):
        Offer(is_free=True, price_max=10)
    assert Offer(is_free=True).price_max is None


def test_occurrence_must_end_after_start():
    start = datetime(2026, 10, 3, 20, tzinfo=timezone.utc)
    with pytest.raises(ValidationError):
        Occurrence(starts_at=start, ends_at=start)


def test_occurrence_requires_timezone():
    with pytest.raises(ValidationError):
        Occurrence(starts_at=datetime(2026, 10, 3, 20))


def test_raw_record_hash_ignores_key_order():
    a = RawRecord(source_id="s", external_id="1", payload={"a": 1, "b": 2})
    b = RawRecord(source_id="s", external_id="1", payload={"b": 2, "a": 1})
    assert a.content_hash == b.content_hash


def test_activity_full():
    activity = Activity(
        title="Concert Candlelight",
        kind=ActivityKind.TEMPORARY,
        venue=Venue(name="Église", postal_code="75004"),
        occurrences=[Occurrence(starts_at=datetime(2026, 10, 3, 19, tzinfo=timezone.utc))],
        offers=[Offer(price_min=35, price_max=55, booking_url="https://example.com/resa", online_booking=True)],
    )
    assert activity.venue.arrondissement == 4
