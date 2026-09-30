from types import SimpleNamespace

import httpx
import pytest
import respx

from surprise import enrich
from surprise.categories import CATEGORIES, categorize

SITE = "https://cabaret.example/"
PAGE = """<html><head>
<meta property="og:image" content="/img/salle.jpg">
<meta name="description" content="Un cabaret &amp; ses revues depuis 1950.">
</head><body></body></html>"""


osm_place = enrich.osm_place


@pytest.fixture(autouse=True)
def no_openstreetmap(monkeypatch):
    monkeypatch.setattr(enrich, "osm_place", lambda *args: None)
    monkeypatch.setattr(enrich, "NOMINATIM_DELAY", 0)


@respx.mock
def test_osm_place_matches_the_postcode_and_skips_streets():
    def result(category, postcode, **extra):
        return {
            "category": category, "name": "Dipsy", "lat": "48.85", "lon": "2.33", "osm_type": "node", "osm_id": 1,
            "address": {"postcode": postcode, "house_number": "11", "road": "Rue Guisarde"}, **extra,
        }

    respx.get(enrich.NOMINATIM_URL).mock(return_value=httpx.Response(200, json=[
        result("highway", "75006"),
        result("amenity", "75011"),
        result("amenity", "75006", extratags={"opening_hours": "Tu-Sa 18:00-02:00"}),
    ]))
    with httpx.Client() as client:
        place = osm_place(client, "Dipsy", "11 rue Guisarde", "75006")
    assert place == {
        "latitude": 48.85, "longitude": 2.33, "opening_hours": "Tu-Sa 18:00-02:00",
        "osm_address": "11 Rue Guisarde", "osm_postal_code": "75006", "osm_url": "https://www.openstreetmap.org/node/1",
    }


def activity(**overrides):
    return {
        "title": "Le Cabaret Imaginaire",
        "kind": "permanent",
        "website": SITE,
        "image": None,
        "categories": ["cabaret"],
        "venue": {"name": "Le Cabaret Imaginaire", "address": "28 rue Exemple", "postal_code": "75005", "arrondissement": 5},
    } | overrides


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ({"title": "Stand-up au Fridge Comedy Club"}, ["humour"]),
        ({"title": "Crazy Horse", "venue_name": "Crazy Horse"}, ["cabaret"]),
        ({"title": "Concert jazz sur une péniche"}, ["concert", "croisiere"]),
        ({"title": "Le Cid", "venue_name": "Théâtre Hébertot"}, ["theatre"]),
        ({"title": "Lancer de hache entre amis"}, ["sensations"]),
        ({"title": "Nocturne", "tags": ["Expo", "Nuit"]}, ["expo", "nuit"]),
        ({"title": "Le Mask", "section": "bar-restaurant/bar"}, ["bar"]),
        ({"title": "Assemblée générale"}, []),
    ],
)
def test_categorize(args, expected):
    assert categorize(**args) == expected
    assert set(expected) <= CATEGORIES.keys()


@respx.mock
def test_site_preview_reads_og_image_and_description():
    respx.get(SITE).mock(return_value=httpx.Response(200, text=PAGE, headers={"content-type": "text/html"}))
    with httpx.Client() as client:
        preview = enrich.site_preview(client, SITE)
    assert preview.image_url == "https://cabaret.example/img/salle.jpg"
    assert preview.description == "Un cabaret & ses revues depuis 1950."


@respx.mock
def test_site_preview_is_empty_when_the_site_fails():
    respx.get(SITE).mock(side_effect=httpx.ConnectError("dns"))
    with httpx.Client() as client:
        assert enrich.site_preview(client, SITE) == enrich.SitePreview()


@respx.mock
def test_google_place_and_fresh_photo():
    search = respx.post(f"{enrich.PLACES_URL}/places:searchText").mock(
        return_value=httpx.Response(200, json={"places": [{"id": "sans-photo"}, {"id": "ChIJ-cabaret", "photos": [{}]}]})
    )
    respx.get(f"{enrich.PLACES_URL}/places/ChIJ-cabaret").mock(
        return_value=httpx.Response(
            200, json={"photos": [{"name": "places/ChIJ-cabaret/photos/abc", "authorAttributions": [{"displayName": "Ana"}]}]}
        )
    )
    media = respx.get(f"{enrich.PLACES_URL}/places/ChIJ-cabaret/photos/abc/media").mock(
        return_value=httpx.Response(200, json={"photoUri": "https://lh3.googleusercontent.com/p/abc"})
    )
    with httpx.Client() as client:
        assert enrich.find_place(client, "test-key", "Le Cabaret Imaginaire 28 rue Exemple 75005 Paris") == "ChIJ-cabaret"
        photo = enrich.place_photo(client, "test-key", "ChIJ-cabaret")
    assert search.calls.last.request.headers["X-Goog-Api-Key"] == "test-key"
    assert media.calls.last.request.url.params["skipHttpRedirect"] == "true"
    assert photo == {"photo_uri": "https://lh3.googleusercontent.com/p/abc", "attribution": "Ana"}


@respx.mock
def test_enrich_one_uses_the_official_site_then_the_describer():
    respx.get(SITE).mock(return_value=httpx.Response(200, text=PAGE, headers={"content-type": "text/html"}))
    seen = {}

    def describer(act, text):
        seen["text"] = text
        return "Une revue de cabaret dans le 5e."

    with httpx.Client() as client:
        fields = enrich.enrich_one({"activity": activity(), "source_text": None}, client, describer=describer)
    assert fields["image_url"] == "https://cabaret.example/img/salle.jpg"
    assert fields["image_origin"] == SITE
    assert fields["description"] == "Une revue de cabaret dans le 5e."
    # Without a licensed source text, the official site's excerpt is what gets rewritten.
    assert seen["text"] == "Un cabaret & ses revues depuis 1950."


@respx.mock
def test_enrich_one_keeps_the_source_image_and_text():
    site = respx.get(SITE).mock(return_value=httpx.Response(200, text=PAGE, headers={"content-type": "text/html"}))
    item = {
        "activity": activity(image={"url": "https://cdn.paris.fr/x.jpg"}, offers=[{"booking_url": "https://billets.example/1"}]),
        "source_text": "Texte ODbL.",
    }
    with httpx.Client() as client:
        fields = enrich.enrich_one(item, client, describer=lambda act, text: text.upper())
    assert not site.called
    assert "image_url" not in fields
    assert fields["description"] == "TEXTE ODBL."


@respx.mock
def test_enrich_one_follows_a_show_page_to_its_buy_button():
    show = "https://gaite.example/spectacles/la-claque/"
    respx.get(show).mock(return_value=httpx.Response(200, headers={"content-type": "text/html"}, text=(
        '<a href="https://themisweb.example/fListeManifs.aspx?id=264">Billetterie</a>'
        '<a href="https://gaite.example/reservation-groupes/">Réservation groupes</a>'
        '<a href="https://themisweb.example/fEventChoiceIsMade.aspx?idevent=333">ACHETER</a>'
    )))
    item = {"activity": activity(image={"url": "https://cdn.paris.fr/x.jpg"}, offers=[{"booking_url": show}]), "source_text": "Texte."}
    with httpx.Client() as client:
        fields = enrich.enrich_one(item, client)
    assert fields["booking_url"] == "https://themisweb.example/fEventChoiceIsMade.aspx?idevent=333"


def test_booking_link_skips_another_event_of_the_listing():
    page = '<a href="/evenements/cyclo-teuf-124231">Réserver</a><a href="https://billets.example/expo">Réservez votre billet</a>'
    assert enrich.booking_link("https://www.paris.fr/evenements/expo-nature-1", page) == "https://billets.example/expo"


@respx.mock
def test_enrich_one_ignores_a_social_profile_as_official_site():
    instagram = respx.get(url__startswith="https://www.instagram.com/")
    item = {"activity": activity(website="https://www.instagram.com/dipsy.paris"), "source_text": None}
    with httpx.Client() as client:
        fields = enrich.enrich_one(item, client, describer=lambda act, text: text)
    assert not instagram.called
    assert not fields.get("image_url") and not fields.get("description")


def test_booking_link_prefers_the_booking_button():
    page = (
        '<a href="https://billetterie-lepic.mapado.com/">Bon Cadeau</a>'
        '<a href="/programmation/">Programmation</a>'
        '<a href="https://billetterie-lepic.mapado.com/event/805990-larmes">Réservez votre place</a>'
    )
    assert enrich.booking_link("https://theatrelepic.com/p/", page) == "https://billetterie-lepic.mapado.com/event/805990-larmes"
    assert enrich.booking_link("https://x.example/", '<a href="https://www.eventbrite.fr/e/123">Infos</a>') == "https://www.eventbrite.fr/e/123"
    assert enrich.booking_link("https://x.example/", '<a href="#resa">Réserver</a><a href="https://shotgun.live/">Shotgun</a>') is None


def test_booking_link_names_the_activity_on_a_programme_page():
    # A JavaScript-built theatre site: every show's ticketing link sits in JSON.
    page = '{"G":"https://www.billetweb.fr/mozart-moi-jamais"},{"G":"https://www.billetweb.fr/adjani-les-murmures-de-l-ame"}'
    title = "Isabelle Adjani, Les murmures de l’âme"
    assert enrich.booking_link("https://studio.example/adjani", page, title) == "https://www.billetweb.fr/adjani-les-murmures-de-l-ame"
    assert enrich.booking_link("https://studio.example/adjani", page, "Un autre spectacle") is None


@respx.mock
def test_enrich_one_finds_the_official_site_booking_link():
    page = '<html><a href="https://billets.example/event/42">Réserver</a></html>'
    respx.get(SITE).mock(return_value=httpx.Response(200, text=page, headers={"content-type": "text/html"}))
    with httpx.Client() as client:
        fields = enrich.enrich_one({"activity": activity(image={"url": "https://cdn.example/x.jpg"}), "source_text": None}, client)
    assert fields["booking_url"] == "https://billets.example/event/42"


@respx.mock
def test_enrich_one_falls_back_on_google_places():
    respx.get(SITE).mock(return_value=httpx.Response(404))
    respx.post(f"{enrich.PLACES_URL}/places:searchText").mock(
        return_value=httpx.Response(200, json={"places": [{"id": "ChIJ-cabaret", "photos": [{}]}]})
    )
    with httpx.Client() as client:
        fields = enrich.enrich_one({"activity": activity(), "source_text": None}, client, places_key="test-key")
    assert fields["place_id"] == "ChIJ-cabaret"
    assert "description" not in fields


class FakeMessages:
    def __init__(self, response):
        self.response, self.kwargs = response, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def fake_client(stop_reason="end_turn", text="« Une revue intimiste au cœur du 5e. »"):
    blocks = [SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)]
    messages = FakeMessages(SimpleNamespace(stop_reason=stop_reason, content=blocks))
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def test_describe_sends_facts_and_source_and_cleans_the_answer():
    client, messages = fake_client()
    text = enrich.describe(client, "claude-opus-5-5", activity(), "<p>Un cabaret &amp; ses revues.</p>")
    assert text == "Une revue intimiste au cœur du 5e."
    prompt = messages.kwargs["messages"][0]["content"]
    assert "Titre : Le Cabaret Imaginaire" in prompt
    assert "Type : Cabaret / music-hall" in prompt
    assert "Un cabaret & ses revues." in prompt
    assert messages.kwargs["model"] == "claude-opus-5-5"
    assert messages.kwargs["fallbacks"] == "default"


def test_describe_ignores_refusals():
    client, _ = fake_client(stop_reason="refusal")
    assert enrich.describe(client, "claude-opus-5-5", activity(), "texte") is None


def test_a_bracketed_template_in_a_page_is_no_link():
    # Accor Arena's script: "https://[domain]/…" made urlsplit raise "Invalid IPv6 URL".
    page = '<script>var u = "https://[domain]/tickets";</script><a href="https://www.ticketmaster.fr/fr/manifestation/x">Réserver</a>'
    assert enrich.booking_link("https://www.accorarena.com/fr/programmation/x", page) == "https://www.ticketmaster.fr/fr/manifestation/x"


def test_match_place_by_distance_then_postcode_then_unique_name():
    def place(lat, postcode=None, url="n/1"):
        return {"latitude": lat, "longitude": 2.35, "opening_hours": None, "osm_address": None, "osm_postal_code": postcode, "osm_url": url}

    index = {
        "dipsy": [place(48.85, url="n/1"), place(48.86, url="n/2")],
        "chez nous": [place(48.87, "75011", "n/3"), place(48.87, "75006", "n/4")],
        "unique": [place(48.88, url="n/5")],
    }
    near = {"name": "Le Dipsy", "postal_code": "75006", "latitude": 48.8601, "longitude": 2.35}
    assert enrich.match_place(index, near)["osm_url"] == "n/2"
    # Coordinates given, but no place of that name close by.
    assert enrich.match_place(index, near | {"latitude": 48.80}) is None
    assert enrich.match_place(index, {"name": "Chez Nous !", "postal_code": "75006"})["osm_url"] == "n/4"
    assert enrich.match_place(index, {"name": "Unique", "postal_code": "75018"})["osm_postal_code"] == "75018"
    # Two untagged places of that name: which one is unknown.
    assert enrich.match_place(index, {"name": "Dipsy", "postal_code": "75006"}) is None


def test_an_event_with_coordinates_skips_openstreetmap(monkeypatch):
    asked = []
    monkeypatch.setattr(enrich, "venue_place", lambda client, venue: asked.append(venue))
    venue = activity()["venue"] | {"latitude": 48.85, "longitude": 2.34}
    item = {"activity": activity(website=None, image={"url": "x"}, kind="temporary", venue=venue), "source_text": None}
    enrich.enrich_one(item, httpx.Client())
    assert not asked
    enrich.enrich_one(item | {"activity": item["activity"] | {"kind": "permanent"}}, httpx.Client())
    assert asked
