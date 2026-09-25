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
    with httpx.Client() as client:
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
