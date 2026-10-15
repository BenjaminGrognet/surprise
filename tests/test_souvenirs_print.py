import json
from datetime import date, datetime, time

import httpx
import pytest
import respx
from PIL import Image, ImageFilter

from surprise import souvenirs_print as sp
from surprise.souvenirs_print import API, EXAMPLE, PARIS, Evening, Printify, Stop


def photo(size=(3024, 4032)) -> Image.Image:
    return sp.demo_photo(1, 800).resize(size)


def test_polaris_stands_at_the_latitude_of_paris_due_north():
    alt, az, _ = sp.sky_positions(datetime(2026, 10, 14, 23, 0, tzinfo=PARIS))["Polaris"]
    assert alt == pytest.approx(sp.PARIS_LAT, abs=1.2)
    assert min(az, 360 - az) < 2


def test_the_sky_turns_with_the_hour():
    early = sp.sky_positions(datetime(2026, 10, 14, 20, 0, tzinfo=PARIS))
    late = sp.sky_positions(datetime(2026, 10, 15, 2, 0, tzinfo=PARIS))
    assert "Betelgeuse" not in early and "Betelgeuse" in late  # Orion rises in the night in October
    assert all(alt >= 0 for alt, _, _ in late.values())


def test_the_sky_of_a_night_out_after_midnight_is_the_next_day():
    evening = Evening("A & B", date(2026, 10, 14), [Stop(time(21), "x", 0, 0), Stop(time(1, 30), "y", 0, 0)])
    assert sp.night_moment(evening) == datetime(2026, 10, 15, 1, 30, tzinfo=PARIS)
    assert sp.night_moment(EXAMPLE) == datetime(2026, 10, 14, 23, 15, tzinfo=PARIS)


@pytest.mark.parametrize("souvenir", sp.SOUVENIRS, ids=lambda s: s.key)
@pytest.mark.parametrize("size", [(900, 900), (1540, 2130), (2362, 709)])
def test_each_souvenir_fills_the_printers_area_exactly(souvenir, size):
    evening = Evening("Camille & Léo", date(2026, 10, 14), EXAMPLE.stops, [photo()])
    design = souvenir.compose(evening, size)
    assert design.size == size and design.mode == "RGB"


def test_the_plaque_shows_the_photo_without_one_a_demo():
    with_photo = sp.plaque(Evening("A & B", EXAMPLE.day, EXAMPLE.stops, [Image.new("RGB", (2000, 2000), (200, 0, 0))]), (1540, 2130))
    assert with_photo.getpixel((770, 500))[0] > 150  # the red photo, under the title
    assert sp.plaque(EXAMPLE, (1540, 2130)).size == (1540, 2130)


def test_print_quality_from_the_enlargement():
    assert sp.print_quality((4032, 3024), (900, 900)) == "parfaite"
    assert sp.print_quality((4032, 3024), (3508, 4961)) == "correcte"
    assert sp.print_quality((1200, 900), (3508, 4961)) == "trop juste"


def test_a_shaken_photo_is_less_sharp():
    sharp = photo((1600, 1200))
    blurred = sharp.filter(ImageFilter.GaussianBlur(8))
    assert sp.sharpness(blurred) < sp.sharpness(sharp)


def test_the_most_precise_search_wins_then_the_shortest_title():
    blueprints = [{"id": 1, "title": "Acrylic Wall Art Panels"}, {"id": 2, "title": "Acrylic Sign with Wood Base"},
                  {"id": 3, "title": "Acrylic Plaque"}, {"id": 4, "title": "Kiss-Cut Magnets"}]
    assert sp.find_blueprint(blueprints, sp.by_key("plaque").searches)["id"] == 2
    assert sp.find_blueprint(blueprints, sp.by_key("magnet").searches)["id"] == 4
    assert sp.find_blueprint(blueprints, sp.by_key("bougie").searches) is None


@respx.mock
def test_drafts_are_made_in_the_shop_by_a_european_provider(tmp_path, monkeypatch):
    monkeypatch.delenv("PRINTIFY_SHOP_ID", raising=False)
    respx.get(f"{API}/shops.json").respond(json=[{"id": 77, "title": "Brouillons"}])
    respx.get(f"{API}/catalog/blueprints.json").respond(json=[{"id": 10, "title": "Square Magnet"}, {"id": 11, "title": "T-shirt"}])
    respx.get(f"{API}/catalog/blueprints/10/print_providers.json").respond(json=[{"id": 1, "title": "US Print"}, {"id": 2, "title": "Riga Print"}])
    respx.get(f"{API}/catalog/print_providers/1.json").respond(json={"id": 1, "location": {"country": "US"}})
    respx.get(f"{API}/catalog/print_providers/2.json").respond(json={"id": 2, "location": {"country": "LV"}})
    respx.get(f"{API}/catalog/blueprints/10/print_providers/2/variants.json").respond(
        json={"variants": [{"id": 501, "title": "3x3", "placeholders": [{"position": "front", "width": 1050, "height": 1050}]}]})
    upload = respx.post(f"{API}/uploads/images.json").respond(json={"id": "img-1"})
    create = respx.post(f"{API}/shops/77/products.json").respond(json={"id": "p-9", "images": [{"src": "https://mock/1.jpg"}]})

    evening = Evening("Camille & Léo", date(2026, 10, 14), EXAMPLE.stops, [photo()])
    drafts = sp.make_drafts(Printify("t", httpx.Client()), evening, ["magnet", "bougie"], tmp_path)

    assert [d.souvenir.key for d in drafts] == ["magnet"]  # no candle in this catalogue
    draft = drafts[0]
    assert (draft.choice.provider["id"], draft.choice.country, draft.choice.size) == (2, "LV", (1050, 1050))
    assert draft.product_id == "p-9" and draft.mockups == ["https://mock/1.jpg"] and draft.quality == "parfaite"
    assert upload.calls[0].request.headers["Authorization"] == "Bearer t"
    body = json.loads(create.calls[0].request.content)
    assert body["blueprint_id"] == 10 and body["print_provider_id"] == 2
    assert body["variants"] == [{"id": 501, "price": 900, "is_enabled": True}]
    assert body["print_areas"][0]["placeholders"][0]["images"][0]["id"] == "img-1"
    assert "publish" not in body and "Brouillon" in body["description"]
    assert Image.open(tmp_path / "magnet.png").size == (1050, 1050)
    assert not any("orders" in str(call.request.url) or "publish" in str(call.request.url) for call in respx.calls)


@respx.mock
def test_a_souvenir_made_only_outside_the_union_is_left_out():
    respx.get(f"{API}/catalog/blueprints/10/print_providers.json").respond(json=[{"id": 1, "title": "US Print"}])
    respx.get(f"{API}/catalog/print_providers/1.json").respond(json={"id": 1, "location": {"country": "US"}})
    blueprints = [{"id": 10, "title": "Square Magnet"}]
    assert sp.choose(Printify("t", httpx.Client()), sp.by_key("magnet"), blueprints) is None


@respx.mock
def test_a_fixed_souvenir_takes_its_product_provider_and_variant():
    respx.get(f"{API}/catalog/blueprints/896/print_providers.json").respond(json=[{"id": 30, "title": "OPT OnDemand"}])
    respx.get(f"{API}/catalog/print_providers/30.json").respond(json={"id": 30, "location": {"country": "CZ"}})
    respx.get(f"{API}/catalog/blueprints/896/print_providers/30/variants.json").respond(json={"variants": [
        {"id": 1, "title": "other", "placeholders": [{"position": "front", "width": 10, "height": 10}]},
        {"id": 77224, "title": "11oz / White", "placeholders": [{"position": "front", "width": 2362, "height": 945}]}]})
    choice = sp.choose(Printify("t", httpx.Client()), sp.by_key("mug"), [{"id": 896, "title": "Heart-Shaped Mug"}])
    assert (choice.variant["id"], choice.country, choice.size) == (77224, "CZ", (2362, 945))
    assert sp.choose(Printify("t", httpx.Client()), sp.by_key("mug"), []) is None  # gone from the catalogue


def test_the_drafts_are_european_by_default_and_a_large_area_is_drawn_smaller():
    assert sp.EUROPEAN == ["plaque", "ciel", "mug"]
    assert sp.design_size((12000, 8250)) == (6000, 4125)
    assert sp.design_size((2362, 945)) == (2362, 945)


def test_the_mug_draws_each_step():
    dots = sp.route_points(EXAMPLE.stops, (0, 0, 100, 100))
    assert len(dots) == 3 and all(0 <= x <= 100 and 0 <= y <= 100 for x, y in dots)
    assert dots[2][0] > dots[0][0]  # Belleville east of the Marais: on the right
    mug = sp.heart_mug(EXAMPLE, (2362, 945))
    paper = sp.PALETTES[sp.DEFAULT_GROUND]
    assert mug.getpixel((5, 470)) == (255, 255, 255)  # all round, the white of the ceramic, whatever the paper
    pixels = set(mug.get_flattened_data())
    assert paper.accent in pixels and paper.gold in pixels  # the stroke, the steps


def test_the_monogram_is_printed_in_gold_on_each_souvenir():
    mask = sp.logo_mask()
    assert mask.getpixel((0, 0)) == 0 and mask.getextrema() == (0, 255)  # the velvet gone, the gold kept
    paper = sp.PALETTES[sp.DEFAULT_GROUND]
    for compose, size in ((sp.plaque, (2000, 3160)), (sp.sky, (2400, 3384)), (sp.heart_mug, (2400, 960))):
        top = compose(EXAMPLE, size).crop((size[0] * 0.4, 0, size[0] * 0.6, size[1] * 0.12))
        assert paper.gold in set(top.get_flattened_data()), compose.__name__


def test_the_secret_name_and_the_clues_are_drawn():
    base = Evening("A & B", EXAMPLE.day, EXAMPLE.stops, title="Le Pacte de l'Île Saint-Louis", clues=["Un indice."])
    other_title = Evening("A & B", EXAMPLE.day, EXAMPLE.stops, title="Le Secret de Montmartre", clues=["Un indice."])
    other_clues = Evening("A & B", EXAMPLE.day, EXAMPLE.stops, title=base.title, clues=["Un autre indice, bien plus long."])
    for compose in (sp.plaque, sp.heart_mug, sp.sky):
        assert compose(base, (600, 800)).tobytes() != compose(other_title, (600, 800)).tobytes()
    assert sp.sky(base, (600, 800)).tobytes() != sp.sky(other_clues, (600, 800)).tobytes()
    assert sp.plaque(base, (600, 800)).tobytes() == sp.plaque(other_clues, (600, 800)).tobytes()  # no clue on the plaque
    assert base.weekday_day == "Mercredi 14 octobre 2026"


@pytest.mark.parametrize("ground", list(sp.PALETTES))
def test_each_ground_paints_every_souvenir(ground):
    evening = Evening("A & B", EXAMPLE.day, EXAMPLE.stops, title=EXAMPLE.title, clues=EXAMPLE.clues, palette=ground)
    for compose in (sp.plaque, sp.sky):
        assert compose(evening, (600, 800)).getpixel((2, 400)) == sp.PALETTES[ground].ground
    assert set(sp.GROUNDS) == set(sp.PALETTES)


def test_the_sheet_sets_each_ground_on_its_row():
    colours = {"casse": (246, 242, 233), "blanc": (10, 20, 30)}  # the second told apart from the sheet's own paper
    made = {(k, g): Image.new("RGB", (300, 400), colours[g]) for k in ("plaque", "mug") for g in colours}
    sheet = sp.sheet(made, ["plaque", "mug"], list(colours))
    assert sheet.getpixel((40 + 350, 40 + 350)) == colours["casse"]
    assert sheet.getpixel((40 + 350, 40 + 700 + 40 + 60 + 350)) == colours["blanc"]


@respx.mock
def test_a_refused_draft_says_why():
    respx.get(f"{API}/shops.json").respond(json=[])
    with pytest.raises(RuntimeError, match="Aucune boutique"):
        Printify("t", httpx.Client()).shop_id()
    respx.post(f"{API}/uploads/images.json").respond(400, json={"error": "too big"})
    with pytest.raises(RuntimeError, match="too big"):
        Printify("t", httpx.Client()).upload("x.jpg", Image.new("RGB", (10, 10)))
