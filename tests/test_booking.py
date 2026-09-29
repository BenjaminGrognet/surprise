import httpx
import respx

from surprise.booking import booking_engine, engine_in
from surprise.collectors.common import Normalized, require_booking
from surprise.models import Activity, RawRecord


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
def test_booking_engine_links_then_pages():
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
        assert booking_engine(client, ["https://karaoke.example/"]) == "billetterie du lieu"
        assert booking_engine(client, ["https://billetterie.opera-comique.com/list/events"]) == "billetterie du lieu"
        assert booking_engine(client, ["https://perpette.example/reserver/"]) == "Bookeo"
        # The site's "Réserver" page embeds the widget.
        assert booking_engine(client, ["https://perpette.example/"]) == "Bookeo"
        assert booking_engine(client, ["https://salle.example/"]) is None


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
    checks = PageChecks({"https://connu.example/": ("Zenchef", False)})
    with httpx.Client() as client:
        assert [booking_engine(client, ["https://club.example/"], checks) for _ in range(3)] == ["billetterie du lieu"] * 3
        assert booking_engine(client, ["https://connu.example/"], checks) == "Zenchef"  # kept from the store: not read
    assert site.call_count == 1
    assert checks.new == {"https://club.example/": ("billetterie du lieu", False)}


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
