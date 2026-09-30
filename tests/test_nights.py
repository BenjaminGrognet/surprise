"""Nights out: hotel and love-room collectors, and the room that ends an evening."""

import json
from datetime import date, datetime, timezone

from surprise import parcours
from surprise.booking import engine_in, is_walk_in
from surprise.collectors import nuits_couple, time_out_hotels
from surprise.models import Activity
from test_parcours import _night, at, item

NOW = datetime(2026, 9, 26, tzinfo=timezone.utc)


def _ld(node):
    return f'<script type="application/ld+json">{json.dumps(node)}</script>'


def test_time_out_hotel_is_named_by_its_page_title_and_priced_by_the_night():
    page = _ld({
        "@type": "Review",
        "headline": "La cachette la plus sexy de Paris est un hôtel",
        "reviewBody": "Un hôtel design à la réputation sulfureuse.",
        "itemReviewed": {
            "@type": "Place", "name": "La cachette la plus sexy de Paris est un hôtel",
            "address": {"streetAddress": "10 rue de Bruxelles", "postalCode": "75009"},
            "geo": {"latitude": 48.88, "longitude": 2.33}, "url": "https://www.maisonsouquet.com",
        },
    }) + "<h1>Maison Souquet</h1><p>De 392,50 à 3 280 € la nuit</p>"
    payload = time_out_hotels.parse_hotel("https://www.timeout.fr/paris/hotels/maison-souquet", page)
    activity = time_out_hotels.normalize(payload, NOW).activity
    assert activity.title == "Maison Souquet" and "hotel" in activity.categories
    offer = activity.offers[0]
    assert (offer.price_min, offer.price_max, offer.price_unit) == (392.5, 3280, "per_couple")

    scale_only = page.replace("De 392,50 à 3 280 € la nuit", '"keywords":["Prix: €€€"]')
    payload = time_out_hotels.parse_hotel("https://www.timeout.fr/paris/hotels/maison-souquet", scale_only)
    assert payload["price_min"] is None and payload["price_label"] == "Prix : €€€"


def test_love_room_catalogue_page_gives_place_price_and_booking():
    page = _ld({
        "@type": "LodgingBusiness", "name": "Suite Jungle", "description": "Spa privatif et sauna.",
        "address": {"streetAddress": "12 rue Oberkampf", "postalCode": "75011", "addressLocality": "Paris"},
        "geo": {"latitude": "48.865", "longitude": "2.37"}, "image": ["https://www.loveroomers.fr/a.jpg"],
        "makesOffer": {"lowPrice": "180", "highPrice": "230"},
        "amenityFeature": [{"name": "spa privatif", "value": True}],
    }) + '<a href="https://booking.loveroomers.fr/55097%20">Réserver</a>'
    payload = nuits_couple.parse_room("https://www.loveroomers.fr/loveroom/paris/paris/suite-jungle/", page)
    assert payload["booking_url"] == "https://booking.loveroomers.fr/55097" and engine_in(payload["booking_url"]) == "Loveroomers"
    activity = nuits_couple.normalize(payload, NOW).activity
    assert activity.venue.arrondissement == 11 and activity.categories == ["hotel"]
    assert activity.offers[0].price_min == 180 and activity.offers[0].price_unit == "per_couple"


def test_a_hotel_bar_is_not_walked_into_the_room_is_booked():
    hotel = Activity(title="Hôtel et son bar", kind="permanent", categories=["bar", "hotel"])
    assert not is_walk_in(hotel) and is_walk_in(Activity(title="Bar", kind="permanent", categories=["bar"]))


def _room(external_id, title, price, lat=48.8622, lon=2.35):
    room = item(external_id, title, ["hotel"], kind="permanent", price=price, lat=lat, lon=lon)
    room["activity"]["offers"][0]["price_unit"] = "per_couple"
    return room


def test_the_evening_ends_in_a_room_near_its_last_step():
    req, _, route = _night()
    req.overnight = True
    route.request = req
    rooms = [
        _room("love", "Suite avec spa privatif", 180),
        _room("palace", "Palace", 1200),
        _room("loin", "Cabane dans les arbres", 120, lat=48.95, lon=2.6),
    ]
    base = parcours.Base(rooms, {(r["source_id"], r["external_id"]): 35 for r in rooms})
    assert parcours.build_candidate(rooms[0], req, None) is None  # never a step of the evening itself

    other = parcours.Route(list(route.steps), request=req)
    parcours.add_nights([route, other], parcours.hotels(base))
    night = route.night
    assert night.candidate.key[1] == "love" and night.start == route.steps[-1].end + parcours.timedelta(minutes=night.travel)
    assert night.end == at(11, day=date(2026, 10, 10))
    assert other.night is None  # not the same room twice; too far or far above the night's budget, never

    # The night's budget is added to the evening's: 1.5 times its 150 €, or as asked.
    assert req.room_budget == 220
    other.request = parcours.Request(**{**req.__dict__, "night_budget": 1100})
    parcours.add_nights([other], [c for c in parcours.hotels(base) if c.key[1] != "love"])
    assert other.night.candidate.key[1] == "palace"

    parcours.name_by_rules(route, req)
    night = parcours.route_json(0, route)["night"]
    assert night["role"] == "nuit" and night["price"] == 180 and not night["price_estimated"] and "on découche" in route.pitch
