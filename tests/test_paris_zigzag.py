from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from surprise.collectors import paris_zigzag as zz

ARTICLE_URL = "https://www.pariszigzag.fr/top-redac/sorties-test/"
PAGE = (Path(__file__).parent / "fixtures" / "paris_zigzag_article.html").read_text(encoding="utf-8")
NOW = datetime(2026, 9, 24, 10, tzinfo=timezone.utc)
TODAY = date(2026, 9, 24)


def results():
    return {p["name"]: zz.normalize(p, NOW) for p in zz.parse_article(ARTICLE_URL, PAGE, "2026-09-20T10:00:00+02:00")}


def test_only_practical_blocks_in_paris_are_read():
    payloads = zz.parse_article(ARTICLE_URL, PAGE)
    assert [p["name"] for p in payloads] == [
        "Le Cabaret Imaginaire",
        "La Pièce Inventée",
        "Festival Test",
        "Infos pratiques",
        "Salon Passé",
    ]
    # Facts only: no editorial paragraph ends up in the payload.
    assert all("éditorial" not in str(p) for p in payloads)


def test_permanent_place_with_bare_address():
    result = results()["Le Cabaret Imaginaire"]
    activity = result.activity
    assert result.raw.external_id == "top-redac/sorties-test#le-cabaret-imaginaire"
    assert str(result.raw.url) == ARTICLE_URL
    assert activity.kind == "permanent"
    assert (activity.venue.name, activity.venue.address, activity.venue.arrondissement) == (
        "Le Cabaret Imaginaire",
        "28 rue du Cardinal Lemoine",
        5,
    )
    # Tracking parameters are dropped from the official link.
    assert str(activity.website) == "https://cabaret.example/billetterie"


def test_show_with_venue_season_and_price_range():
    activity = results()["La Pièce Inventée"].activity
    assert (activity.venue.name, activity.venue.address, activity.venue.postal_code) == (
        "Théâtre Fictif",
        "5 rue La Bruyère",
        "75009",
    )
    assert (activity.starts_on, activity.ends_on) == (date(2026, 9, 19), date(2027, 6, 27))
    offer = activity.offers[0]
    assert (offer.price_min, offer.price_max) == (Decimal("24"), Decimal("45"))
    assert str(offer.booking_url) == "https://billets.example/piece"
    assert str(activity.website) == "https://theatre.example/piece"


def test_venue_on_its_own_line_hours_and_free_entry():
    activity = results()["Festival Test"].activity
    assert (activity.venue.name, activity.venue.address) == ("Hippodrome Imaginaire", "2 route de la Ferme")
    assert (activity.starts_on, activity.ends_on) == (None, date(2026, 10, 30))
    assert activity.is_evening is True
    assert activity.offers[0].is_free is True


def test_generic_heading_takes_the_venue_name():
    activity = results()["Infos pratiques"].activity
    assert activity.title == "Bar Secret"
    assert activity.kind == "permanent"
    # "de 18h à 2h": closing after midnight.
    assert activity.is_evening is True
    assert activity.venue.address == "1 rue de Marengo"


def test_past_events_are_rejected():
    assert results()["Salon Passé"].rejection == "passé"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Du vendredi 25 au dimanche 27 septembre 2026", (date(2026, 9, 25), date(2026, 9, 27))),
        ("Du 19 septembre 2026 au 30 mai 2027", (date(2026, 9, 19), date(2027, 5, 30))),
        ("Du 19 septembre au 27 juin 2027", (date(2026, 9, 19), date(2027, 6, 27))),
        # A typo for 2027 on the site: the season cannot end before it starts.
        ("Du 9 septembre au 16 janvier 2026.", (date(2026, 9, 9), date(2027, 1, 16))),
        ("Jusqu'au au 18 octobre 2026", (None, date(2026, 10, 18))),
        ("À partir du 1er octobre", (date(2026, 10, 1), None)),
        ("Les 19 et 20 septembre 2026", (date(2026, 9, 19), date(2026, 9, 20))),
        ("Le 12 mars", (date(2027, 3, 12), date(2027, 3, 12))),
        ("Toute l'année", (None, None)),
        ("Lundi à 21h, mardi à 19h jusqu'au 27 octobre 2026", (None, date(2026, 10, 27))),
    ],
)
def test_parse_dates(text, expected):
    assert zz.parse_dates(text, TODAY) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Théâtre Marigny, Carré Marigny 75008 Paris", ("Théâtre Marigny", "Carré Marigny")),
        ("RDC de l'Hôtel, 51/53 Quai de Grenelle, 75015 Paris", ("RDC de l'Hôtel", "51/53 Quai de Grenelle")),
        ("La Nouvelle Seine, sur berges, face au 3 Quai de Montebello 75005 Paris", ("La Nouvelle Seine, sur berges", "3 Quai de Montebello")),
        ("12 Av. George V 75008 Paris", ("Nom par défaut", "12 Av. George V")),
    ],
)
def test_split_venue(text, expected):
    assert zz.split_venue(text, default_name="Nom par défaut") == expected


def test_postal_code_from_district():
    assert zz.postal_code("5 rue La Bruyère, Paris 9e") == "75009"
    assert zz.postal_code("1 place de Valois, Paris 1er") == "75001"
    assert zz.postal_code("3 place Test, 93100 Montreuil") is None


def test_venue_written_as_a_label():
    page = "<p><strong>Soirée Test</strong><br />Le Gratin : 1 place de Valois, Paris 1er<br />Le 30 septembre 2026 à 19h</p>"
    [payload] = zz.parse_article(ARTICLE_URL, page)
    activity = zz.normalize(payload, NOW).activity
    assert (activity.venue.name, activity.venue.postal_code) == ("Le Gratin", "75001")


def test_image_is_the_last_article_photo_above_the_block():
    uploads = "https://www.pariszigzag.fr/wp-content/uploads/2026/08"
    page = (
        f'<img class="wp-image-1" src="{uploads}/a.webp" />'
        "<p><strong>Bar A</strong><br />1 rue Test, 75006 Paris</p>"
        f'<img src="{uploads}/b.webp" class="size-full wp-image-2" />'
        "<p><strong>Bar B</strong><br />2 rue Test, 75006 Paris</p>"
        f'<img class="wp-post-image" src="{uploads}/related-150x150.webp" />'
    )
    a, b = (zz.normalize(p, NOW).activity for p in zz.parse_article(ARTICLE_URL, page))
    assert (str(a.image.url), str(b.image.url)) == (f"{uploads}/a.webp", f"{uploads}/b.webp")
    assert results()["Le Cabaret Imaginaire"].activity.image is None


@respx.mock
def test_collect_reads_recent_articles_in_scope():
    respx.get(zz.SITEMAP_INDEX).mock(
        return_value=httpx.Response(
            200,
            text="<sitemapindex>"
            "<sitemap><loc>https://www.pariszigzag.fr/post-sitemap1.xml</loc><lastmod>2026-09-23T20:00:00+02:00</lastmod></sitemap>"
            "<sitemap><loc>https://www.pariszigzag.fr/post-sitemap2.xml</loc><lastmod>2026-03-30T15:00:00+02:00</lastmod></sitemap>"
            "<sitemap><loc>https://www.pariszigzag.fr/page-sitemap1.xml</loc><lastmod>2026-09-22T15:00:00+02:00</lastmod></sitemap>"
            "</sitemapindex>",
        )
    )
    respx.get("https://www.pariszigzag.fr/post-sitemap1.xml").mock(
        return_value=httpx.Response(
            200,
            text="<urlset>"
            f"<url><loc>{ARTICLE_URL}</loc><lastmod>2026-09-20T10:00:00+02:00</lastmod></url>"
            "<url><loc>https://www.pariszigzag.fr/famille/atelier-enfants/</loc><lastmod>2026-09-21T10:00:00+02:00</lastmod></url>"
            "<url><loc>https://www.pariszigzag.fr/lyon-actu/expo/</loc><lastmod>2026-09-21T10:00:00+02:00</lastmod></url>"
            "<url><loc>https://www.pariszigzag.fr/insolite/vieil-article/</loc><lastmod>2026-05-01T10:00:00+02:00</lastmod></url>"
            "</urlset>",
        )
    )
    article = respx.get(ARTICLE_URL).mock(return_value=httpx.Response(200, text=PAGE))
    with httpx.Client() as client:
        collected = list(zz.collect(client, NOW, delay=0))
    assert article.call_count == 1
    assert len(collected) == 5
    assert {r.raw.source_id for r in collected} == {"paris_zigzag"}
