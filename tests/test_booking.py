import json
from datetime import datetime, timezone

import httpx
import respx

from surprise.availability import FUNBOOKER_API
from surprise.booking import booking_found, engine_in, slot_check
from surprise.collectors.common import Normalized, require_booking
from surprise.models import Activity, BookingMode, RawRecord


def test_engine_in_links():
    assert engine_in("https://feverup.com/m/716002") == "Fever"
    assert engine_in("https://www.billetweb.fr/shop.php?event=gravure-sceau") == "Billetweb"
    assert engine_in("https://www.billetterie-parismusees.paris.fr/selection/timeslotpass?productId=1") == "Secutix"
    assert engine_in("https://bookings.zenchef.com/results?rid=351778") == "Zenchef"
    assert engine_in('<div class="forescape-catalog" data-widget-id="0e20" data-settings="b64.e30="></div>') == "4escape"
    assert engine_in("https://theatredelavilleparis.notre-billetterie.com/billets?seance=706") == "Notre Billetterie"
    assert engine_in("https://simdrivers.qweekle.com/shop/simdrivers/") == "Qweekle"
    assert engine_in("https://www.orchestrehelios.com/concerts") is None
    # An association's page is not a ticketing form.
    assert engine_in("https://centredaide.helloasso.com/particulier?question=billet") is None


@respx.mock
def test_booking_found_in_links_then_pages():
    respx.get("https://perpette.example/reserver/").mock(
        return_value=httpx.Response(200, text='<script src="https://bookeo.com/widget.js?a=32506C9T6C18CF8FBCA73"></script>')
    )
    respx.get("https://perpette.example/").mock(
        return_value=httpx.Response(200, text='<a href="/reserver/">Réserver</a>', headers={"content-type": "text/html"})
    )
    respx.get("https://salle.example/").mock(return_value=httpx.Response(200, text="<p>Réservation par téléphone</p>"))
    respx.get("https://karaoke.example/").mock(
        return_value=httpx.Response(200, text='<a href="https://booking.karaoke.example/booking?lang=fr">Réserver</a>')
    )
    with httpx.Client() as client:
        # The "Réserver" button leads to the venue's own booking site.
        assert booking_found(client, ["https://karaoke.example/"]) == ("billetterie du lieu", None)
        assert booking_found(client, ["https://billetterie.opera-comique.com/list/events"]) == ("billetterie du lieu", None)
        assert booking_found(client, ["https://perpette.example/reserver/"]) == ("Bookeo", None)
        # The site's "Réserver" page embeds the widget.
        assert booking_found(client, ["https://perpette.example/"]) == ("Bookeo", None)
        assert booking_found(client, ["https://salle.example/"]) is None


def normalized(**offer):
    raw = RawRecord(source_id="paris_zigzag", external_id="x", payload={})
    return Normalized(raw, activity=Activity(title="Un lieu", kind="permanent", offers=[offer] if offer else []))


@respx.mock
def test_require_booking_keeps_free_or_bookable():
    respx.get("https://salle.example/").mock(return_value=httpx.Response(200, text="<p>Venez !</p>"))
    with httpx.Client() as client:
        assert require_booking(client, normalized(is_free=True)).activity
        assert require_booking(client, normalized(booking_url="https://shotgun.live/fr/events/guinguette")).activity
        rejected = require_booking(client, normalized(booking_url="https://salle.example/", price_min=20))
        # Kept with its reason, to be reviewed apart in moderation.
        assert (rejected.activity.title, rejected.rejection) == ("Un lieu", "ni gratuit ni réservable en ligne")
        assert require_booking(client, normalized()).rejection == "ni gratuit ni réservable en ligne"


@respx.mock
def test_require_booking_keeps_open_walk_in_places():
    respx.get("https://bar.example/").mock(return_value=httpx.Response(200, text="<p>Ouvert du mardi au samedi</p>"))
    respx.get("https://ferme.example/").mock(return_value=httpx.Response(200, text="<p>Le bar est fermé définitivement.</p>"))

    def place(website, category="bar"):
        raw = RawRecord(source_id="paris_zigzag", external_id=website, payload={})
        activity = Activity(title="Un bar", kind="permanent", website=website, categories=[category], offers=[{"price_min": 8}])
        return Normalized(raw, activity=activity)

    with httpx.Client() as client:
        kept = require_booking(client, place("https://bar.example/"))
        assert kept.activity.offers[0].online_booking is False
        assert require_booking(client, place("https://bar.example/", "restaurant")).activity
        assert require_booking(client, place("https://ferme.example/")).rejection == "fermé définitivement"
        # Not a walk-in place: still needs online booking.
        assert require_booking(client, place("https://bar.example/", "expo")).rejection == "ni gratuit ni réservable en ligne"


def test_a_page_with_an_inline_image_is_read_quickly():
    import time

    from surprise.booking import booking_form

    # A 1 MB base64 photo in the page: "[\w-]+\.qweekle" tried at each of its letters took hours.
    page = '<img src="data:image/png;base64,' + "A" * 1_000_000 + '"> <a href="https://x.qweekle.com/shop/">Réserver</a>'
    started = time.perf_counter()
    assert engine_in(page) == "Qweekle"
    assert booking_form("https://site.example/", page) is None
    assert time.perf_counter() - started < 2


@respx.mock
def test_each_page_is_read_once_per_run():
    from surprise.booking import PageChecks

    site = respx.get("https://club.example/").mock(
        return_value=httpx.Response(200, text='<a href="https://billetterie.club.example/">Billets</a>')
    )
    checks = PageChecks({"https://connu.example/": ("Zenchef", False, "zenchef:353900")})
    with httpx.Client() as client:
        assert [booking_found(client, ["https://club.example/"], checks) for _ in range(3)] == [("billetterie du lieu", None)] * 3
        assert booking_found(client, ["https://connu.example/"], checks) == ("Zenchef", "zenchef:353900")  # kept from the store: not read
    assert site.call_count == 1
    assert checks.new == {"https://club.example/": ("billetterie du lieu", False, None)}


def test_a_venue_ticketing_page_and_an_organiser_booking_form_count_as_online_booking():
    from surprise.booking import booking_form, own_ticketing

    assert own_ticketing("https://www.musee-jacquemart-andre.com/fr/tickets/6a280a225308177b77141dd9") == "billetterie du lieu"
    assert own_ticketing("https://www.musee-jacquemart-andre.com/fr/eternel-tintoret") is None
    page = '<p>Réservation préalable impérative : <a href="https://forms.gle/UkU56kpyD2eZZtF86">formulaire</a></p>'
    assert booking_form("https://www.coree-culture.org/ateliers", page) == "formulaire de réservation"
    assert booking_form("https://example.org", '<a href="https://forms.gle/x">Votre avis sur le site</a>') is None


def test_a_venue_selling_its_seats_on_its_own_ticketing_or_page():
    from surprise.booking import engine_in, ticketing_of_site
    from surprise.enrich import _is_deep_link

    page = '<a href="https://billetterie.38riv.com/concorde/@customer">Mon compte</a>'
    assert ticketing_of_site("https://38riv.com/concerts/herbin", page) == "billetterie du lieu"
    assert ticketing_of_site("https://38riv.com/concerts/herbin", '<a href="https://billetterie.autre.com/">x</a>') is None
    assert engine_in('<form id="tribe-tickets__tickets-form" action="…">') == "Event Tickets"
    assert _is_deep_link("https://lemelville.fr/?p=6098") and not _is_deep_link("https://lemelville.fr/?lang=en")


def test_slot_checks_in_widgets_and_listing_links():
    assert slot_check("https://bookings.zenchef.com/results?rid=351778&pid=1001") == "zenchef:351778"
    assert slot_check('<a href="https://bookings.zenchef.com/results?lang=fr&amp;rid=353900">') == "zenchef:353900"
    assert slot_check("https://www.sevenrooms.com/reservations/sienarestaurant") == "sevenrooms:sienarestaurant"
    # {"domain":"activeroom-paris.4escape.io"}
    settings = '<div class="forescape-catalog" data-widget-id="7175" data-settings="b64.eyJkb21haW4iOiJhY3RpdmVyb29tLXBhcmlzLjRlc2NhcGUuaW8ifQ=="></div>'
    assert slot_check(settings) == "4escape:activeroom-paris.4escape.io"
    assert slot_check('<div class="forescape" data-subdomain="wyb-immersion" data-type="bookings">') == "4escape:wyb-immersion.4escape.io"
    assert slot_check('<a href="https://www.4escape.io">Propulsé par 4escape</a>') is None
    # A platform's listing counts by its link, not because a page mentions it.
    funbooker = "https://www.funbooker.com/fr/annonce/atelier-gravure-a-paris-18eme/voir"
    assert slot_check(funbooker, link=True) == "funbooker:atelier-gravure-a-paris-18eme"
    assert slot_check(f'<a href="{funbooker}">', link=False) is None
    assert slot_check("https://wecandoo.fr/atelier/paris-parfum", link=True) == "wecandoo:https://wecandoo.fr/atelier/paris-parfum"
    ctp = "https://www.cometoparis.com/fre/musees-et-monuments/musee-des-arts-decoratifs-m9001137"
    assert slot_check(ctp, link=True) == f"come_to_paris:{ctp}"


@respx.mock
def test_a_widget_engine_gives_its_venue_id_from_the_reserver_page():
    # The site names Zenchef (its script) and books on its "Réserver" page, where the restaurant's id is.
    respx.get("https://casa-loca.example/").mock(return_value=httpx.Response(
        200, text='<script src="https://sdk.zenchef.com/v1/sdk.min.js"></script><a href="/reservation/">Réserver</a>',
    ))
    respx.get("https://casa-loca.example/reservation/").mock(
        return_value=httpx.Response(200, text='<iframe src="https://bookings.zenchef.com/results?rid=353900&amp;pid=1001">')
    )
    respx.get("https://down.example/").mock(side_effect=httpx.ConnectError("dns"))
    respx.get("https://widget.zenchef.com/x").mock(return_value=httpx.Response(404))
    with httpx.Client() as client:
        assert booking_found(client, ["https://down.example/", "https://casa-loca.example/"]) == ("Zenchef", "zenchef:353900")
        # A widget's link without the id: the official site gives it.
        assert booking_found(client, ["https://widget.zenchef.com/x", "https://casa-loca.example/"]) == ("Zenchef", "zenchef:353900")


@respx.mock
def test_each_activity_says_how_it_is_booked():
    respx.get("https://bar.example/").mock(return_value=httpx.Response(200, text="<p>Ouvert du mardi au samedi</p>"))
    with httpx.Client() as client:
        def mode(**offer):
            booking = require_booking(client, normalized(**offer)).activity.booking
            return booking.mode, booking.engine, booking.check

        assert mode(is_free=True) == (BookingMode.FREE, None, None)
        assert mode(booking_url="https://shotgun.live/fr/events/guinguette") == (BookingMode.TICKETING, "Shotgun", None)
        assert mode(booking_url="https://bookings.zenchef.com/results?rid=351778") == (BookingMode.SLOT, "Zenchef", "zenchef:351778")
        respx.get(f"{FUNBOOKER_API}/listing/color-room-a-paris-9eme").mock(return_value=httpx.Response(200, json={"id": 24, "listingItems": [
            {"id": 10, "label": "Duo", "priceType": "plan", "numberOfPersons": 2, "isOption": False},
            {"id": 11, "label": "Photo souvenir", "priceType": "per_person", "isOption": True},
        ]}))
        listing = "https://www.funbooker.com/fr/annonce/color-room-a-paris-9eme/voir"
        booked, engine, check = mode(booking_url=listing)
        # The listing's id and items, read at collection: an evening asks only for the slots, for any party.
        assert (booked, engine, json.loads(check.removeprefix("funbooker:"))) == (BookingMode.SLOT, "Funbooker", {
            "slug": "color-room-a-paris-9eme", "listing": 24,
            "items": [{"id": 10, "label": "Duo", "priceType": "plan", "minCapacity": None, "maxCapacity": None, "numberOfPersons": 2}],
        })
        raw = RawRecord(source_id="paris_zigzag", external_id="bar", payload={})
        bar = Activity(title="Un bar", kind="permanent", website="https://bar.example/", categories=["bar"], offers=[{"price_min": 8}])
        assert require_booking(client, Normalized(raw, activity=bar)).activity.booking.mode == BookingMode.WALK_IN


def test_wecandoo_books_its_workshops_by_their_id():
    from surprise.collectors import wecandoo

    url = "https://wecandoo.fr/atelier/paris-parfum"
    payload = {"url": url, "workshop_id": 4512, "name": "Créez votre parfum en duo", "website": url, "booking_url": url,
               "price_min": 90, "venue_name": "Atelier", "address": "1 rue de Paris", "postal_code": "75011"}
    activity = wecandoo.normalize(payload, datetime(2026, 10, 4, tzinfo=timezone.utc)).activity
    assert (activity.booking.mode, activity.booking.check) == (BookingMode.SLOT, "wecandoo:4512")
