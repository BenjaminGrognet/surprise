import json
from datetime import date

import httpx
import respx

from surprise import availability
from surprise.booking import PageChecks

DAY = date(2026, 10, 9)
FUNBOOKER_LISTING = f"{availability.FUNBOOKER_API}/listing/escape-game-a-paris-2eme"
FUNBOOKER_SLOTS = f"{availability.FUNBOOKER_API}/availabilities"


def item(id, price_type, persons=1, low=0, high=10, **extra):
    return {
        "id": id, "label": f"formule {id}", "priceType": price_type, "numberOfPersons": persons,
        "minCapacity": low, "maxCapacity": high, "isOption": False, "isDisabled": False, **extra,
    }


def slot(start, available=True, capacity=8):
    return {"localDateTimeStart": f"2026-10-09T{start}:00", "allDay": False, "available": available, "capacity": capacity}


def test_funbooker_capacities_seat_two():
    items = [
        item(1, "per_person", high=1),  # individual massage
        item(2, "plan", persons=3),
        item(3, "plan", persons=2),
        item(4, "per_person", low=2, high=20),
        item(5, "per_person", isOption=True),
    ]
    assert availability._funbooker_capacities(items, 2) == [("formule 3", {"3": 1}), ("formule 4", {"4": 2})]


@respx.mock
def test_funbooker_tries_each_item_for_two():
    respx.get(FUNBOOKER_LISTING).mock(return_value=httpx.Response(200, json={
        "id": 24, "listingItems": [item(10, "plan", persons=2), item(11, "per_person")],
    }))
    slots = respx.post(FUNBOOKER_SLOTS).mock(side_effect=[
        httpx.Response(200, json={"availabilities": [slot("11:00", available=False)]}),
        httpx.Response(200, json={"availabilities": [slot("14:00"), slot("16:00", capacity=1), slot("18:00")]}),
    ])
    with httpx.Client() as client:
        result = availability.check_funbooker(client, "escape-game-a-paris-2eme", DAY)
    assert (result.available, result.slots, result.detail) == (True, ["14:00", "18:00"], "formule 11")
    assert json.loads(slots.calls[0].request.content) == {
        "listingId": 24, "capacities": {"10": 1}, "day": "2026-10-09", "includeAllFutureDates": False,
    }


KNOWN = "funbooker:" + json.dumps({
    "slug": "escape-game-a-paris-2eme", "listing": 24, "items": [item(10, "plan", persons=2), item(12, "per_person", low=4, high=6)],
})


@respx.mock
def test_funbooker_items_known_at_collection_ask_only_the_slots():
    listing = respx.get(FUNBOOKER_LISTING)
    slots = respx.post(FUNBOOKER_SLOTS).mock(return_value=httpx.Response(200, json={"availabilities": [slot("20:00")]}))
    workshop = {"activity": {"booking": {"mode": "creneau", "check": KNOWN}}}
    with httpx.Client() as client:
        assert availability.check(client, workshop, DAY, 2) == ("Funbooker", availability.Availability(True, ["20:00"], "formule 10"))
        # A group asks the items that seat it, known as well.
        assert availability.check(client, workshop, DAY, 5)[1].detail == "formule 12"
    assert listing.call_count == 0
    assert [json.loads(call.request.content)["capacities"] for call in slots.calls] == [{"10": 1}, {"12": 5}]


@respx.mock
def test_funbooker_items_changed_since_the_collection_are_read_again():
    listing = respx.get(FUNBOOKER_LISTING).mock(return_value=httpx.Response(200, json={"id": 24, "listingItems": [item(13, "per_person")]}))
    respx.post(FUNBOOKER_SLOTS).mock(side_effect=lambda request: httpx.Response(
        200 if "13" in json.loads(request.content)["capacities"] else 400, json={"availabilities": [slot("21:00")]},
    ))
    with httpx.Client() as client:
        result = availability.check_funbooker(client, KNOWN.removeprefix("funbooker:"), DAY)
    assert (result.available, result.detail, listing.call_count) == (True, "formule 13", 1)


@respx.mock
def test_funbooker_listing_read_once_at_collection():
    listing = respx.get(FUNBOOKER_LISTING).mock(side_effect=[
        httpx.Response(503), httpx.Response(200, json={"id": 24, "listingItems": [item(10, "plan", persons=2)]}),
    ])
    with httpx.Client() as client:
        # Not answering: the slug is kept, the listing will be read at the evening's check.
        assert availability.known_check(client, "funbooker:escape-game-a-paris-2eme", PageChecks()) == "funbooker:escape-game-a-paris-2eme"
        checks = PageChecks()
        found = availability.known_check(client, "funbooker:escape-game-a-paris-2eme", checks)
        assert json.loads(found.removeprefix("funbooker:"))["listing"] == 24
        # Once per run, then kept with the page verdicts (page_checks).
        assert availability.known_check(client, "funbooker:escape-game-a-paris-2eme", checks) == found
        assert list(checks.new.values()) == [("Funbooker", False, found)]
        assert availability.known_check(client, "zenchef:351778", checks) == "zenchef:351778"
    assert listing.call_count == 2


@respx.mock
def test_funbooker_full_day():
    respx.get(FUNBOOKER_LISTING).mock(return_value=httpx.Response(200, json={"id": 24, "listingItems": [item(11, "per_person")]}))
    respx.post(FUNBOOKER_SLOTS).mock(return_value=httpx.Response(200, json={"availabilities": []}))
    with httpx.Client() as client:
        assert availability.check_funbooker(client, "escape-game-a-paris-2eme", DAY).available is False


CTP_URL = "https://www.cometoparis.com/fre/musees-et-monuments/sainte-chapelle-m9000587"
CTP_PAGE = """
<div class="product_box product_container  unavailable sold_out multiple_price" data-product_id="2160" data-name="2160 - Billet Jumel&eacute;" data-delivery_date_from="">
<div class="product_box product_container active " data-product_id="2151" data-name="2151 - Billet Conciergerie et Bateaux-Mouches" data-delivery_date_from="">
<div class="product_box product_container   is_gift" data-product_id="2692" data-name="2692 - BON CADEAU" data-delivery_date_from="">
<input type="hidden" name="layout_grouping_id" id="layout_grouping_id" value="11596" />
"""


def pax_form(options, full=False):
    choices = "".join(f'<option value="{n}" class=""  data-unit_price="17">\n\t{n}\n</option>' for n in options)
    return (
        '<div class="pax_item"><select class="form-control form-select pax_selector" name="qty[0][17]" id="qty_17"'
        f' data-price_type="17" data-is_main_price="1"  >{choices}</select>\n\t\t'
        f'<div class="full_of_pax_message{"" if full else " hidden"}"><span>Complet</span></div></div>'
    )


HOUR_FORM = (
    '<label class="radiobutton bold "><input type="radio" value="10:00:00" name="booking_hour" checked="checked" data-combination="" />'
    '<label class="radiobutton bold "><input type="radio" value="14:30:00" name="booking_hour" data-combination="" />'
)


def come_to_paris(dated):
    requests = []

    def booking(request):
        body = json.loads(request.content)
        requests.append(body)
        if body["action"] == "set_current_booking_product":
            return httpx.Response(200, json={
                "no_api_response": False,
                "calendar_available_price": {"2026-10-08": 8, "2026-10-09": 8},
                "calendar_date_closings": {"2026-10-08": {}},
            })
        return httpx.Response(200, json=dated)

    respx.get(CTP_URL).mock(return_value=httpx.Response(200, text=CTP_PAGE))
    respx.post(availability.COME_TO_PARIS_AJAX).mock(side_effect=booking)
    with httpx.Client() as client:
        return availability.check_come_to_paris(client, CTP_URL, DAY), requests


@respx.mock
def test_come_to_paris_hours_for_two():
    result, requests = come_to_paris({"has_no_disponibilities": False, "product_hour_form": HOUR_FORM, "product_pax_form": pax_form(range(11))})
    assert (result.available, result.slots, result.detail) == (True, ["10:00", "14:30"], "Billet Conciergerie et Bateaux-Mouches")
    # Only the formula on sale, then its date, midnight in Paris.
    assert [(r["action"], r["product_id"]) for r in requests] == [
        ("set_current_booking_product", "2151"), ("set_current_booking_date", "2151"),
    ]
    assert requests[0]["product_list"] == ["2160", "2151", "2692"] and requests[0]["layout_grouping_id"] == "11596"
    assert (requests[1]["date"], requests[1]["french_date"]) == (1791496800, "2026-10-9")


@respx.mock
def test_come_to_paris_sold_out_or_single_ticket():
    assert come_to_paris({"product_pax_form": pax_form(range(11), full=True)})[0].available is False
    assert come_to_paris({"product_pax_form": pax_form(range(2))})[0].available is False
    result = come_to_paris({"product_pax_form": pax_form(range(3))})[0]
    assert (result.available, result.slots) == (True, ["journée"])


@respx.mock
def test_come_to_paris_product_off_sale():
    respx.get(CTP_URL).mock(return_value=httpx.Response(200, text='<h2>Indisponible</h2><p>Ce produit est complet.</p>'))
    with httpx.Client() as client:
        result = availability.check_come_to_paris(client, CTP_URL, DAY)
    assert (result.available, result.detail) == (False, "plus en vente")


@respx.mock
def test_come_to_paris_checks_keep_their_own_session():
    # The form's state is in the session: two checks at once must not share it.
    page = respx.get(CTP_URL).mock(return_value=httpx.Response(200, text="<h2>Indisponible</h2>", headers={"Set-Cookie": "PHPSESSID=a; Path=/"}))
    with httpx.Client() as client:
        availability.check_come_to_paris(client, CTP_URL, DAY)
        availability.check_come_to_paris(client, CTP_URL, DAY)
        assert not client.cookies
    assert "cookie" not in page.calls[1].request.headers


@respx.mock
def test_come_to_paris_closed_day():
    respx.get(CTP_URL).mock(return_value=httpx.Response(200, text=CTP_PAGE))
    booking = respx.post(availability.COME_TO_PARIS_AJAX).mock(return_value=httpx.Response(200, json={
        "calendar_available_price": {"2026-10-09": 8}, "calendar_date_closings": {"2026-10-09": {}},
    }))
    with httpx.Client() as client:
        assert availability.check_come_to_paris(client, CTP_URL, DAY).available is False
    assert booking.call_count == 1


def zenchef_slot(name, guests=(2, 3, 4), **extra):
    return {"name": name, "closed": False, "marked_as_full": False, "possible_guests": list(guests), **extra}


@respx.mock
def test_zenchef_services_open_to_two():
    route = respx.get(availability.ZENCHEF_API).mock(return_value=httpx.Response(200, json=[{"date": "2026-10-09", "shifts": [
        {"name": "Brunch", "closed": False, "marked_as_full": False, "shift_slots": [zenchef_slot("10:45", guests=(4, 5, 6))]},
        {"name": "Déjeuner", "closed": False, "marked_as_full": False, "shift_slots": [
            zenchef_slot("12:00"), zenchef_slot("12:15", marked_as_full=True), zenchef_slot("12:30"),
        ]},
        {"name": "Dîner", "closed": False, "marked_as_full": True, "shift_slots": [zenchef_slot("19:00")]},
    ]}]))
    with httpx.Client() as client:
        result = availability.check_zenchef(client, "351778", DAY)
    assert (result.available, result.slots, result.detail) == (True, ["12:00", "12:30"], "Déjeuner")
    assert route.calls[0].request.url.params["restaurantId"] == "351778"


@respx.mock
def test_zenchef_closed_day():
    respx.get(availability.ZENCHEF_API).mock(return_value=httpx.Response(200, json=[{"date": "2026-10-09", "isOpen": "closed", "shifts": []}]))
    with httpx.Client() as client:
        assert availability.check_zenchef(client, "351778", DAY).available is False


@respx.mock
def test_sevenrooms_bookable_times_only():
    def time(hour, kind):
        return {"type": kind, "time_iso": f"2026-10-09 {hour}:00"}

    route = respx.get(availability.SEVENROOMS_API).mock(return_value=httpx.Response(200, json={"data": {"availability": {"2026-10-09": [
        {"name": "DEJEUNER", "is_closed": False, "times": [time("11:30", "request"), time("12:00", "book")]},
        {"name": "DINER", "is_closed": False, "times": [time("18:00", "book"), time("18:15", "request")]},
    ]}}}))
    with httpx.Client() as client:
        result = availability.check_sevenrooms(client, "sienarestaurant", DAY)
    assert (result.available, result.slots, result.detail) == (True, ["12:00", "18:00"], "DEJEUNER, DINER")
    assert route.calls[0].request.url.params["party_size"] == "2"


@respx.mock
def test_4escape_sessions_with_places_for_two():
    respx.get("https://activeroom-paris.4escape.io/api/public/settings").mock(return_value=httpx.Response(200, json={"rooms": {
        "quiz": {"name": "RIVAL QUIZ", "customer_categories_allowed": [{"minimum_players": 3}]},
        "grid": {"name": "Grid 1", "customer_categories_allowed": [{"minimum_players": 0}]},
        "trip": {"name": "The Trip", "customer_categories_allowed": []},
    }}))

    def session(room, start, **extra):
        return {"roomId": room, "start": f"2026-10-09 {start}:00", "booked": False, "disabled": False, "private": True,
                "remainingPlayers": 10, **extra}

    respx.post("https://activeroom-paris.4escape.io/booking-data-json").mock(return_value=httpx.Response(200, json={"results": [
        session("quiz", "18:00"),  # 3 players minimum
        session("grid", "18:30"),
        session("grid", "19:00", booked=True, remainingTeams=0, remainingPlayers=0),  # taken
        session("grid", "19:30", disabled=True),
        session("trip", "20:15", booked=True, remainingTeams=4, remainingPlayers=7),  # places left
        session("trip", "21:00", remainingPlayers=1),
    ]}))
    with httpx.Client() as client:
        result = availability.check_4escape(client, "activeroom-paris.4escape.io", DAY)
    assert (result.available, result.slots, result.detail) == (True, ["18:30", "20:15"], "Grid 1, The Trip")


@respx.mock
def test_wecandoo_keeps_sessions_with_two_seats_left():
    url = "https://wecandoo.fr/atelier/paris-parfum"
    respx.get(url).mock(return_value=httpx.Response(200, text='<div :page-props="{&quot;workshop&quot;:{&quot;id&quot;:4512,">'))
    event = lambda start, end, taken, **extra: {"start": f"2026-10-09T{start}:00+02:00", "end": f"2026-10-09T{end}:00+02:00", "capacity": 10, "taken_seats": taken, "is_full": False, **extra}
    events = respx.get(availability.WECANDOO_EVENTS.format(4512)).mock(return_value=httpx.Response(200, json={"data": [
        event("10:30", "12:30", 9),
        event("14:00", "16:00", 3, is_full=True),
        event("19:00", "21:00", 8),
    ]}))
    with httpx.Client() as client:
        result = availability.check_wecandoo(client, url, DAY)
        # Its id known at collection: no page to read.
        assert availability.check_wecandoo(client, "4512", DAY) == result
    assert (result.available, result.slots) == (True, ["19:00-21:00"])
    assert events.calls[0].request.url.params["start"] == "2026-10-09T00:00:00+02:00"
    assert respx.calls.call_count == 3


@respx.mock
def test_the_engine_asked_is_the_one_found_at_collection():
    events = respx.get(availability.WECANDOO_EVENTS.format(4512)).mock(return_value=httpx.Response(200, json={"data": []}))
    workshop = {"source_id": "selections_couple", "activity": {"booking": {"mode": "creneau", "check": "wecandoo:4512"}}}
    with httpx.Client() as client:
        assert availability.check(client, workshop, DAY, 2)[0] == "Wecandoo"
        assert availability.check(client, {"activity": {"booking": {"mode": "billetterie", "engine": "Fever"}}}, DAY, 2) is None
        assert availability.check(client, {"activity": {}}, DAY, 2) is None
    assert events.call_count == 1
