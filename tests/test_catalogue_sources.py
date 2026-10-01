import argparse
import gzip
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
import respx

from surprise import collect, renormalize
from surprise.collectors import civitatis, eventbrite, fever, getyourguide, le_bonbon, tiqets, visit_paris_region
from surprise.local_store import LocalStore

NOW = datetime(2026, 9, 25, 10, tzinfo=timezone.utc)


def ld(node):
    return f'<script type="application/ld+json">{json.dumps(node)}</script>'


def urlset(*locs):
    return "<urlset>" + "".join(f"<url><loc>{loc}</loc></url>" for loc in locs) + "</urlset>"


@respx.mock
def test_fever_plan_ids_and_series_pages():
    respx.get(fever.CITY_PAGES[0]).mock(return_value=httpx.Response(200, text='<a href="/fr/m/12"><a href="https://feverup.com/m/34"><a href="/m/12">'))
    with httpx.Client() as client:
        assert fever.fetch_plan_ids(client) == ["12", "34"]
    page = ld({"@type": "Event", "name": "Candlelight", "description": "Lieu : Maison de l'Océan (Paris 5)", "startDate": "2026-10-02",
               "location": {"name": "Maison de l'Océan", "geo": {"latitude": 48.84, "longitude": 2.34}},
               "offers": [{"price": "35"}, {"price": "25"}, {"price": ""}], "image": {"contentUrl": "https://img/x.jpg"}})
    payload = fever.parse_plan("12", page)
    assert (payload["postal_code"], payload["price_min"], payload["price_max"], payload["image_url"]) == ("75005", 25.0, 35.0, "https://img/x.jpg")
    assert fever.normalize(payload, NOW).activity.venue.postal_code == "75005"
    assert fever.normalize(fever.parse_plan("56", "<html></html>"), NOW).rejection == "page de série"


@respx.mock
def test_civitatis_keeps_activities_not_category_pages():
    respx.get(civitatis.SITEMAP).mock(return_value=httpx.Response(200, text=urlset(
        "https://www.civitatis.com/fr/paris/croisiere-seine/", "https://www.civitatis.com/fr/paris/excursions/",
        "https://www.civitatis.com/fr/londres/tour/", "https://www.civitatis.com/fr/paris/croisiere-seine/",
    )))
    with httpx.Client() as client:
        assert civitatis.fetch_activity_urls(client) == ["https://www.civitatis.com/fr/paris/croisiere-seine/"]
    page = ld({"@type": "Product", "name": "Croisière sur la Seine", "offers": {"price": 15}, "image": ["https://img/a.jpg"],
               "description": "Une croisière."}) + r'\"address\":\"\",\"short_address\":\"Port de la Bourdonnais.\",\"gps\":{\"latitude\":48.86,\"longitude\":2.29}'
    payload = civitatis.parse_activity("https://www.civitatis.com/fr/paris/croisiere-seine/", page)
    assert (payload["slug"], payload["venue_name"], payload["latitude"], payload["image_url"]) == ("croisiere-seine", "Port de la Bourdonnais", "48.86", "https://img/a.jpg")
    assert civitatis.normalize(payload | {"postal_code": "75007"}, NOW).activity.title == "Croisière sur la Seine"
    assert civitatis.normalize({"url": "https://www.civitatis.com/fr/paris/balades/", "slug": "balades"}, NOW).rejection == "page de catégorie"


@respx.mock
def test_tiqets_venue_from_ticket_name():
    respx.get(tiqets.SITEMAP).mock(return_value=httpx.Response(200, content=gzip.compress(urlset(
        "https://www.tiqets.com/fr/attractions-paris-c66746/billets-pour-le-musee-grevin-p123/",
        "https://www.tiqets.com/fr/attractions-londres-c1/x-p9/",
    ).encode())))
    with httpx.Client() as client:
        [url] = tiqets.fetch_product_urls(client)
    payload = tiqets.parse_product(url, ld({"@type": "Product", "name": "Billets pour le Musée Grévin : coupe-file", "offers": {"price": 25}}))
    assert (payload["product_id"], payload["venue_name"], payload["price_min"]) == ("123", "Musée Grévin", 25)
    assert tiqets.normalize(payload | {"name": ""}, NOW).rejection == "page illisible"


@respx.mock
def test_getyourguide_reads_activity_sitemaps_and_meeting_point():
    respx.get(getyourguide.SITEMAP_INDEX).mock(return_value=httpx.Response(200, text=urlset("https://gyg/sitemap-activity-1.xml", "https://gyg/sitemap-blog.xml")))
    respx.get("https://gyg/sitemap-activity-1.xml").mock(return_value=httpx.Response(200, text=urlset(
        "https://www.getyourguide.com/fr-fr/paris-l16/croisiere-du-soir-t42/", "https://www.getyourguide.com/fr-fr/rome-l33/x-t1/",
    )))
    with httpx.Client() as client:
        [url] = getyourguide.fetch_activity_urls(client, delay=0)
    page = ld({"@type": "TouristTrip", "name": "Paris : croisière du soir", "offers": {"lowPrice": 18}}) + (
        '<div id="meeting-point-links"><span class="a"><span class="b">Pont d&#39;Iéna.</span></span>'
        '<a href="https://maps.google.com/?q=@48.86,2.29">carte</a></div>'
    )
    payload = getyourguide.parse_activity(url, page)
    assert (payload["activity_id"], payload["venue_name"], payload["longitude"]) == ("42", "Pont d'Iéna", "2.29")
    assert getyourguide.normalize(payload | {"postal_code": "75007"}, NOW).activity.title == "Croisière du soir"
    assert getyourguide.normalize(payload | {"name": None}, NOW).rejection == "page illisible"


@respx.mock
def test_eventbrite_listing_pages_until_nothing_new():
    item = lambda n: {"item": {"url": f"https://www.eventbrite.fr/e/soiree-{n}", "name": f"Soirée {n}", "startDate": "2026-10-02"}}
    listing = lambda *ns: ld({"@type": "ItemList", "itemListElement": [item(n) for n in ns]})
    route = respx.get(eventbrite.SEARCH_URL).mock(side_effect=[httpx.Response(200, text=listing(1, 2)), httpx.Response(200, text=listing(2))])
    with httpx.Client() as client:
        assert [i["name"] for i in eventbrite.fetch_events(client, delay=0)] == ["Soirée 1", "Soirée 2"]
    assert route.call_count == 2

    listed = {"url": "https://www.eventbrite.fr/e/jazz-123", "name": "Jazz", "startDate": "2026-10-02", "endDate": "2026-10-02",
              "location": {"name": "Sunside", "address": {"streetAddress": "60 rue des Lombards", "postalCode": "75001"}}}
    page = ld({"@type": "MusicEvent", "startDate": "2026-10-02T21:00:00+02:00", "offers": [{"lowPrice": "0", "highPrice": "0"}]})
    payload = eventbrite.parse_event(listed, page)
    assert (payload["event_id"], payload["free"], payload["category_text"]) == ("123", True, "MusicEvent")
    activity = eventbrite.normalize(payload, NOW).activity
    assert activity.is_evening and activity.starts_on.isoformat() == "2026-10-02"
    assert "en ligne" in (eventbrite.normalize(payload | {"online": True}, NOW).rejection or "")


@respx.mock
def test_visit_paris_region_place_and_off_topic_breadcrumb():
    respx.get(visit_paris_region.SITEMAP).mock(return_value=httpx.Response(200, text=urlset(
        "https://www.visitparisregion.com/fr/station-f", "https://www.visitparisregion.com/fr/parcours-x",
    )))
    with httpx.Client() as client:
        assert visit_paris_region.fetch_place_urls(client) == ["https://www.visitparisregion.com/fr/station-f"]
    page = """<h1 class="crtBanner-title">Station F</h1><div class="crtBanner-teaser">Le campus.</div>
    <a class="crtBreadcrumb-link" href="#">Sortir</a><address class="crtProductContact-adress">5 parvis Alan Turing<br>75013 Paris</address>
    <div data-latitude="48.83" data-longitude="2.37"></div>
    <div class="crtProductOpeningDays">Du jeudi au samedi de 19h à 2h</section>
    <div class="crtProductPrices">Tarifs Plein tarif : 12 € - 20 €</section>"""
    payload = visit_paris_region.parse_place("https://www.visitparisregion.com/fr/station-f", page)
    assert (payload["name"], payload["price_min"], payload["price_max"], payload["evening"]) == ("Station F", 12.0, 20.0, True)
    assert visit_paris_region.normalize(payload, NOW).activity.venue.postal_code == "75013"
    assert "hors sujet" in visit_paris_region.normalize(payload | {"breadcrumb": ["Hôtels"]}, NOW).rejection


def test_le_bonbon_articles_and_district_alone():
    assert le_bonbon._is_article("https://www.lebonbon.fr/paris/bars/les-meilleurs-bars-a-vin/")
    assert not le_bonbon._is_article("https://www.lebonbon.fr/paris/horoscope/ce-que-disent-les-astres/")
    assert not le_bonbon._is_article("https://www.lebonbon.fr/paris/bars/")
    assert le_bonbon._section("https://www.lebonbon.fr/paris/bars/x-y-z-w/") == "bars"


def test_collect_lists_every_collector_once():
    modules = {path.stem for path in (Path(collect.__file__).parent / "collectors").glob("*.py")} - {"__init__", "common", "facts"}
    assert sorted(collect.SOURCES) == sorted(modules) and len(set(collect.SOURCES)) == len(collect.SOURCES)
    # The project instructions list them all too.
    claude_md = (Path(collect.__file__).parents[2] / "CLAUDE.md").read_text(encoding="utf-8")
    assert set(collect.SOURCES) <= set(re.findall(r"\b[a-z_]+\b", claude_md))


def test_collect_one_reports_a_failing_source(monkeypatch, tmp_path):
    args = argparse.Namespace(db=tmp_path / "s.db", limit=1, refresh=False, minutes=None)
    monkeypatch.setattr(collect, "collect_source", lambda *a: {"retenues": 1})
    assert collect.collect_one("fever", args) == ("fever", {"retenues": 1})
    source_id, error = collect.collect_one("absente", args)
    assert source_id == "absente" and isinstance(error, ModuleNotFoundError)


def test_renormalize_applies_the_rules_again(monkeypatch, tmp_path):
    payload = fever.parse_plan("12", ld({"@type": "Event", "name": "Concert", "location": {"address": {"streetAddress": "1 rue X"}}}))
    monkeypatch.setattr(renormalize, "require_booking", lambda client, result, checks: result)
    with LocalStore(tmp_path / "s.db") as store:
        before = fever.normalize(payload, NOW)
        store.save_raw_records([before.raw])
        store.save_normalized([(before.raw, before.activity, "ancienne règle")])
        changes = renormalize.renormalize(store, sources=["fever"])
        assert changes == {f"ancienne règle → {before.rejection or 'retenue'}": 1}
        assert renormalize.renormalize(store, sources=["tiqets"]) == {}
