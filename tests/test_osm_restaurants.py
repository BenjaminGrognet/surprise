from datetime import datetime, timezone

import httpx
import respx

from surprise.collectors import osm_restaurants

NOW = datetime(2026, 9, 26, 10, tzinfo=timezone.utc)
PLACE = {
    "type": "node",
    "id": 42,
    "lat": 48.8566,
    "lon": 2.3522,
    "tags": {
        "amenity": "restaurant", "name": "Le Petit Bistrot", "cuisine": "french;wine_bar",
        "addr:housenumber": "12", "addr:street": "Rue des Rosiers", "addr:postcode": "75004",
        "website": "lepetitbistrot.fr", "diet:vegetarian": "yes",
    },
}


@respx.mock
def test_site_with_a_zenchef_widget_is_kept():
    respx.get("https://lepetitbistrot.fr").mock(return_value=httpx.Response(200, text=(
        '<meta property="og:image" content="/photo.jpg"><meta name="description" content="Bistrot du Marais">'
        '<a href="https://bookings.zenchef.com/results?rid=1234">Réserver</a>'
    ), headers={"content-type": "text/html"}))
    with httpx.Client() as client:
        site = osm_restaurants.read_site(client, "https://lepetitbistrot.fr")
    assert site["engine"] == "Zenchef" and site["booking_url"] == "https://bookings.zenchef.com/results?rid=1234"
    assert site["image_url"] == "https://lepetitbistrot.fr/photo.jpg" and site["lead_text"] == "Bistrot du Marais"

    activity = osm_restaurants.normalize(osm_restaurants.facts(PLACE, site), NOW).activity
    assert activity.title == "Le Petit Bistrot" and activity.venue.address == "12 Rue des Rosiers"
    assert "restaurant" in activity.categories and activity.venue.postal_code == "75004"


@respx.mock
def test_reserve_page_embeds_the_engine():
    respx.get("https://resto.example/").mock(return_value=httpx.Response(200, text='<a href="/reserver">Réserver une table</a>'))
    respx.get("https://resto.example/reserver").mock(return_value=httpx.Response(200, text='<script src="https://sdk.zenchef.com/v1/sdk.min.js"></script>'))
    with httpx.Client() as client:
        site = osm_restaurants.read_site(client, "https://resto.example/")
    assert site["engine"] == "Zenchef"


@respx.mock
def test_restaurant_without_online_booking_is_rejected():
    respx.get("https://lepetitbistrot.fr").mock(return_value=httpx.Response(200, text="<p>Venez sans réserver</p>"))
    with httpx.Client() as client:
        site = osm_restaurants.read_site(client, "https://lepetitbistrot.fr")
    assert osm_restaurants.normalize(osm_restaurants.facts(PLACE, site), NOW).rejection == "sans réservation en ligne"


def test_engine_link_skips_scripts_and_unescapes():
    page = '<script src="https://sdk.zenchef.com/v1/sdk.min.js"></script><a href="https://bookings.zenchef.com/results?rid=1&amp;pid=1001">'
    assert osm_restaurants._engine_link(page) == "https://bookings.zenchef.com/results?rid=1&pid=1001"
