import json
from datetime import date

import httpx
import respx

from surprise import availability

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
def test_come_to_paris_closed_day():
    respx.get(CTP_URL).mock(return_value=httpx.Response(200, text=CTP_PAGE))
    booking = respx.post(availability.COME_TO_PARIS_AJAX).mock(return_value=httpx.Response(200, json={
        "calendar_available_price": {"2026-10-09": 8}, "calendar_date_closings": {"2026-10-09": {}},
    }))
    with httpx.Client() as client:
        assert availability.check_come_to_paris(client, CTP_URL, DAY).available is False
    assert booking.call_count == 1
