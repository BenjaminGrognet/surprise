import html
import json
from datetime import datetime, timezone

import httpx
import respx

from surprise.collectors import (
    billetreduc,
    concerts_paris,
    explore_paris,
    paris_jetaime,
    paris_jetaime_billetterie,
    privateaser,
    selections_couple,
    selections_squad,
    shotgun,
    wecandoo,
)
from surprise.collectors.facts import address_in_text, ld_node, normalize_facts, nuxt_data
from surprise.models import RawRecord

NOW = datetime(2026, 9, 25, 10, tzinfo=timezone.utc)


def raw(payload):
    return RawRecord(source_id="test", external_id="1", payload=payload)


def test_normalize_facts_rejections():
    # Every reason is kept; a blocking one (no place) ends the fiche, the others let it be built for moderation.
    assert normalize_facts(raw({}), {"name": "Soirée célibataires"}, "x", NOW).rejection == "pas pour un couple · sans lieu"
    workshop = {"name": "Atelier parent-enfant", "address": "1 rue X, 75011 Paris", "ends_on": "2026-09-01"}
    result = normalize_facts(raw({}), workshop, "x", NOW)
    assert result.rejection == "jeune public · passé" and result.activity.title == "Atelier parent-enfant"
    assert normalize_facts(raw({}), {"name": "Visite"}, "x", NOW).rejection == "sans lieu"
    assert normalize_facts(raw({}), {"name": "Visite", "address": "1 rue X, 91300 Massy"}, "x", NOW).rejection == "hors Paris et proche banlieue"
    past = {"name": "Expo", "address": "1 rue X, 75011 Paris", "ends_on": "2026-09-01"}
    assert normalize_facts(raw({}), past, "x", NOW).rejection == "passé"


def test_normalize_facts_evening_show():
    facts = {
        "name": "Concert",
        "venue_name": "YOYO",
        "address": "Palais De Tokyo, 13 Avenue du Président Wilson, 75016 Paris, France",
        "starts_at": "2026-09-26T19:30:00Z",
        "price_min": 20,
        "booking_url": "https://shotgun.live/fr/events/x",
    }
    activity = normalize_facts(raw({}), facts, "Shotgun", NOW).activity
    assert (activity.venue.name, activity.venue.address, activity.venue.postal_code) == ("YOYO", "13 Avenue du Président Wilson", "75016")
    assert activity.is_evening and activity.starts_on.isoformat() == "2026-09-26"
    assert activity.offers[0].online_booking and float(activity.offers[0].price_min) == 20


def test_ld_node_escaped_type_and_address_in_text():
    page = '<script type="application/ld&#x2B;json">{"@type":"TheaterEvent","name":"Pièce"}</script>'
    assert ld_node(page, "Event")["name"] == "Pièce"
    assert address_in_text("Rendez-vous au 12 rue de la Roquette, 75011 Paris à 19h") == "12 rue de la Roquette, 75011 Paris"


def test_nuxt_data():
    values = [{"data": 1}, ["Reactive", 2], {"product": 3}, {"name": 4, "tags": 5}, "Atelier", [4]]
    page = f'<script type="application/json" id="__NUXT_DATA__">{json.dumps(values)}</script>'
    assert nuxt_data(page) == {"data": {"product": {"name": "Atelier", "tags": ["Atelier"]}}}


def test_concerts_paris_event():
    event = {
        "slug": "tour-x",
        "title": "Quatuor",
        "canonicalUrl": "https://concerts.paris/events/tour-x",
        "startDate": "2026-09-26T18:00:00.000Z",
        "endDate": "2026-09-26T18:00:00.000Z",
        "nextDate": "2026-09-26T18:00:00.000Z",
        "venue": {"title": "Salle", "address": {"streetAddress": "3 rue de Lisbonne", "postalCode": "75008"}, "geo": {}},
        "offers": {"price": 25, "url": "https://concerts.paris/go/tickets?event=tour-x", "officialUrl": "https://www.tiqets.com/x"},
        "practical": {"priceType": "payant"},
        "vertical": "concert",
        "genre": "jazz",
    }
    activity = concerts_paris.normalize(event, NOW).activity
    assert activity.is_evening and activity.occurrences[0].starts_at.hour == 18
    assert str(activity.offers[0].booking_url) == "https://www.tiqets.com/x"
    assert "concert" in activity.categories


def test_concerts_paris_run_keeps_its_shows():
    show = lambda start, **extra: {"startDate": start, "eventStatus": "EventScheduled", "offers": {"availability": "InStock"}, **extra}
    event = {
        "slug": "serie-x",
        "title": "Comédie",
        "startDate": "2026-10-01T18:30:00.000Z",
        "endDate": "2026-10-20T18:30:00.000Z",
        "venue": {"title": "Salle", "address": {"streetAddress": "3 rue de Lisbonne", "postalCode": "75008"}, "geo": {}},
        "offers": {"price": 20},
        "practical": {"priceType": "payant"},
        "vertical": "theatre",
        "showDates": [
            show("2026-10-01T18:30:00.000Z"),
            show("2026-10-02T18:30:00.000Z", offers={"availability": "SoldOut"}),
            show("2026-10-03T18:30:00.000Z", eventStatus="EventCancelled"),
            show("2026-10-09T18:30:00.000Z"),
        ],
    }
    activity = concerts_paris.normalize(event, NOW).activity
    assert [o.starts_at.day for o in activity.occurrences] == [1, 9]


def test_paris_jetaime_event():
    event = {
        "id": "expo-x",
        "title": "Expo photo",
        "venue_name": "Maison de la culture du Japon",
        "venue_address": "101 bis quai Jacques Chirac",
        "zipcode": "75015",
        "start_date": "2026-06-09",
        "end_date": "2026-10-26",
        "price_type": "gratuit",
        "categories": ["expositions"],
        "details": {"infos_pratiques": {"reservation": None, "lien_officiel": "https://www.mcjp.fr"}},
    }
    activity = paris_jetaime.normalize(event, NOW).activity
    assert activity.offers[0].is_free and activity.venue.postal_code == "75015" and "expo" in activity.categories


def test_paris_jetaime_billetterie_product():
    # Nuxt's flattened state: every value is an index into the list.
    values = [
        {"data": 1},
        {"key": 2},
        {"productId": 3, "name": 4, "price": 6, "image": 7, "location": 8, "excerpt": 11, "content": 13, "primaryCategory": 15},
        200,
        {"fr": 5},
        "Atelier vin",
        "95.00",
        "products/vin.jpg",
        {"address": 9, "lat": 10, "lng": 10},
        "52 Rue de l'Arbre Sec\r\n75001 Paris",
        "",
        {"fr": 12},
        "Des caves du XVIIIe.",
        {"fr": 14},
        "<p>Créez votre vin.</p>",
        {"name": 16},
        {"fr": 17},
        "Gastronomie",
    ]
    page = f'<script id="__NUXT_DATA__">{json.dumps(values)}</script>'
    url = "https://ticket.parisjetaime.com/gastronomie-c4/atelier-vin-200"
    activity = paris_jetaime_billetterie.normalize(paris_jetaime_billetterie.parse_product(url, page), NOW).activity
    assert (activity.title, activity.venue.address, activity.venue.postal_code) == ("Atelier vin", "52 Rue de l'Arbre Sec", "75001")
    assert str(activity.image.url) == "https://pjt.imgix.net/products/vin.jpg?w=1400"


def test_wecandoo_duo_workshop():
    workshop = {
        "workshop": {
            "nom": "Tournage en duo",
            "prix": 150,
            "duration": 120,
            "format": {"price_for": "duo", "name": "Duo"},
            "tags": [{"slug": "duo"}],
            "lieu": {"nom": "Atelier", "lat": 48.86, "lng": 2.37, "address": {"address1": "8 Rue Édouard-Lockroy", "zip_code": "75011"}},
        }
    }
    page = f':page-props="{html.escape(json.dumps(workshop))}"'
    payload = wecandoo.parse_workshop("https://wecandoo.fr/atelier/paris-x", page)
    activity = wecandoo.normalize(payload, NOW).activity
    assert activity.offers[0].price_unit == "per_couple" and activity.duration_minutes == 120
    parent = payload | {"tags": ["duo-parent-enfant"]}
    assert wecandoo.normalize(parent, NOW).rejection == "jeune public"


def test_billetreduc_run_of_shows():
    page = """<script type="application/ld&#x2B;json">{"@type":"Event","name":"Tout va bien","startDate":"2026-10-16T21:15:00+02:00",
    "endDate":"2027-05-03T21:15:00+02:00","location":{"@type":"Place","name":"Comédie Saint Martin","address":{"streetAddress":
    "33 boulevard Saint Martin","postalCode":"75003"}},"offers":[{"price":"19"},{"price":"32"}],"description":"Une comédie."}</script>
    <div class="event-description-text is-collapsed" id="event-description-text">
      <div>Samy et Manon se marient dans 24&nbsp;heures.</div><div><br></div><div>Tout va bien se passer !</div>
    </div>
    <button type="button" class="event-description-toggle">Lire la suite</button>"""
    url = "https://www.billetreduc.com/spectacle/tout-va-bien-414255"
    payload = billetreduc.parse_show(url, page)
    assert payload["lead_text"] == "Une comédie.\nSamy et Manon se marient dans 24 heures.\nTout va bien se passer !"
    activity = billetreduc.normalize(payload, NOW).activity
    assert activity.kind == "temporary" and activity.is_evening
    assert (float(activity.offers[0].price_min), float(activity.offers[0].price_max)) == (19, 32)


def test_explore_paris_sessions():
    page = """<h1 class="product_name" itemprop="name">Montmartre est une f&ecirc;te</h1>
    <span itemprop="price" content="22"></span>
    <p>Lieu : Paris 18ème</p><p>Durée : 2h</p><p>Accès en transport en commun : Place de Clichy (métro ligne 13)</p>
    <p>Date(s) Samedi 03 octobre 2026 - 18:00 Samedi 03 octobre 2026 - 20:30</p>"""
    payload = explore_paris.locate(None, explore_paris.parse_tour("https://exploreparis.com/fr/8710-x.html", "8710", page))
    activity = explore_paris.normalize(payload, NOW).activity
    assert activity.venue.postal_code == "75018" and activity.duration_minutes == 120
    assert [o.starts_at.hour for o in activity.occurrences] == [18, 20] and activity.is_evening


def test_couple_selection_article():
    page = """<article><h1>Idées</h1>
    <h2>1. Speakeasy : Le Moonshiner</h2><p>Derrière une pizzeria, un bar secret au 5 Rue Sedaine, 75011 Paris.</p>
    <h2>Conseils pratiques</h2><p>Réservez à l'avance pour les soirées du week-end, c'est plus sûr.</p>
    <h2>Les Aventuriers</h2><p>Pour les joueurs :
      <a href="https://hati-hati.fr/page_activite/escape-x">Escape Game Fantastique : 60 minutes</a>
      <a href="https://hati-hati.fr/page_activite/tir-x">Session Tir à l'Arc en duo</a></p>
    </article>"""
    ideas = selections_couple.parse_article("https://blog.example/couple", page)
    assert [idea["name"] for idea in ideas] == ["Speakeasy : Le Moonshiner", "Escape Game Fantastique : 60 minutes", "Session Tir à l'Arc en duo"]
    assert ideas[0]["address"] == "5 Rue Sedaine, 75011 Paris"
    assert ideas[1]["venue_name"] == "Escape Game Fantastique"


def test_band_selection_article():
    """The lists for a band of friends say their places their own way: each read as the place it names."""
    section = "<p>Un endroit parfait pour chanter, boire et rire entre potes jusqu'au bout de la nuit.</p>"
    page = f"""<article><h2>Les meilleurs bars à jeux de Paris</h2>{section}
    <h2>Le plus tardif : la Noche à Pigalle</h2>{section}<a href="https://www.google.fr/maps/place/La+Noche">Plan</a>
    <h2>Miami Boulevard — Paris 1</h2>{section}<a href="https://www.google.com/url?q=https%3A%2F%2Fwww.miami-boulevard.com%2F">site</a>
    <h2>PAN, le premier bar à tir de Paris</h2>{section}
    <h2>Un atelier cocktail au Shake n' Smash</h2>{section}
    <h2>Les Mauvais Joueurs</h2>{section}<p><a href="https://www.privateaser.com/lieu/11602-les-mauvais-joueurs">46 Rue Sedaine, 75011 Paris</a></p>
    <h2>181 Rue Legendre, 75017 Paris</h2>{section}
    <h2>À la Une</h2>{section}<h3>6 bibliothèques climatisées où lire au frais</h3>{section}</article>"""
    ideas = {idea["name"]: idea for idea in selections_couple.parse_article("https://lebonbon.example/tops", page)}
    assert list(ideas) == [
        "La Noche à Pigalle", "Miami Boulevard", "PAN, le premier bar à tir de Paris", "Un atelier cocktail au Shake n' Smash",
        "Les Mauvais Joueurs",
    ]
    # Its place apart from its neighbourhood, a map no site.
    assert (ideas["La Noche à Pigalle"]["venue_name"], ideas["La Noche à Pigalle"]["website"]) == ("La Noche", None)
    # The arrondissement after the name, the site behind a Google redirect.
    assert (ideas["Miami Boulevard"]["postal_code"], ideas["Miami Boulevard"]["website"]) == ("75001", "https://www.miami-boulevard.com/")
    assert ideas["PAN, le premier bar à tir de Paris"]["venue_name"] == "PAN"
    assert ideas["Un atelier cocktail au Shake n' Smash"]["venue_name"] == "Shake n' Smash"
    # A link labelled with the address books the place of the heading.
    assert ideas["Les Mauvais Joueurs"]["booking_url"] == "https://www.privateaser.com/lieu/11602-les-mauvais-joueurs"
    assert ideas["Les Mauvais Joueurs"]["address"] == "46 Rue Sedaine, 75011 Paris"


@respx.mock
def test_a_selected_bar_on_privateaser_takes_its_place_from_it(monkeypatch):
    monkeypatch.setattr(privateaser, "DELAY_SECONDS", 0)
    bar = "https://www.privateaser.com/lieu/11602-les-mauvais-joueurs"
    respx.get(bar).mock(return_value=httpx.Response(200, text="""<h1 itemprop="name">Les Mauvais Joueurs</h1>
      <meta itemprop="postalCode" content="75011"> <meta itemprop="streetAddress" content="46 Rue Sedaine">
      <meta itemprop="latitude" content="48.856"> <meta itemprop="longitude" content="2.373">
      <meta itemprop="openingHours" content="Tu-Sa 17:00-01:00">
      <h3 class="title">Réserver quelques tables</h3> <div class="capacity-block"> 2-40 personnes </div>"""))
    idea = {"article_url": "https://lebonbon.example/tops", "name": "Les Mauvais Joueurs", "booking_url": bar, "website": bar}
    with httpx.Client() as client:
        placed = selections_couple.with_listing(client, idea)
    assert (placed["address"], placed["postal_code"], placed["evening"], placed["players_max"]) == ("46 Rue Sedaine", "75011", True, 40)
    activity = selections_squad.normalize(placed, NOW).activity
    assert (activity.venue.postal_code, activity.players_min, activity.players_max) == ("75011", 2, 40)
    assert selections_squad.to_raw_record(placed).external_id == "lebonbon.example/tops#les-mauvais-joueurs"


@respx.mock
def test_shotgun_asks_the_cumulative_page_until_it_ends():
    page = lambda slugs, more: "".join(f'<a href="/fr/events/{s}">' for s in slugs) + ('<a href="?page=51">' if more else "")
    route = respx.get(shotgun.PARIS_PAGE).mock(side_effect=[
        httpx.Response(200, text=page(["a", "b"], more=True) + '<a href="?page=26">'),
        httpx.Response(200, text=page(["a", "b", "c", "b"], more=False)),
    ])
    with httpx.Client() as client:
        assert shotgun.fetch_event_slugs(client, delay=0) == ["a", "b", "c"]
    assert [call.request.url.params["page"] for call in route.calls] == ["25", "50"]


def test_stag_party_offers_are_tagged_for_a_band():
    from surprise.tags import tag

    def evjf(title: str) -> bool:
        return "evjf" in tag({"title": title, "venue": {"name": ""}, "categories": []})

    assert evjf('SPA insolite "The Beer Spa" formule EVG & EVJF')
    assert evjf("Atelier pour un enterrement de vie de jeune fille")
    assert evjf("La Bringue - Halloween Stripclub Girls Only - Paris")
    assert not evjf("Atelier bougie en duo") and not evjf("Soirée Evgeny Kissin")


def test_stag_party_offers_are_kept_at_collection():
    # A band's (Secret Squad): kept in the base, only a couple's evening leaves them out (parcours.fits_party).
    assert normalize_facts(raw({}), {"name": "Atelier cocktails EVJF", "address": "3 rue X, 75011 Paris"}, "x", NOW).rejection is None


def test_time_out_venue_name_drops_the_page_title():
    from surprise.collectors import time_out

    payload = {"url": "https://www.timeout.fr/paris/restaurants/volver", "name": "Volver | Restaurants à Roquette",
               "venue_name": "Volver | Restaurants à Roquette", "address": "1 rue de la Roquette", "postal_code": "75011"}
    activity = time_out.normalize(payload, datetime(2026, 9, 30, tzinfo=timezone.utc)).activity
    assert activity.venue.name == "Volver"
