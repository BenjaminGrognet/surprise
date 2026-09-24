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


def test_booking_link_prefers_the_booking_button():
    page = (
        '<a href="https://billetterie-lepic.mapado.com/">Bon Cadeau</a>'
        '<a href="/programmation/">Programmation</a>'
        '<a href="https://billetterie-lepic.mapado.com/event/805990-larmes">Réservez votre place</a>'
    )
    assert enrich.booking_link("https://theatrelepic.com/p/", page) == "https://billetterie-lepic.mapado.com/event/805990-larmes"
    assert enrich.booking_link("https://x.example/", '<a href="https://www.eventbrite.fr/e/123">Infos</a>') == "https://www.eventbrite.fr/e/123"
    assert enrich.booking_link("https://x.example/", '<a href="#resa">Réserver</a><a href="https://shotgun.live/">Shotgun</a>') is None


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
