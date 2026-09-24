from datetime import date, datetime, timezone

from surprise.collectors import funbooker, paris_city_game, paris_friendly

NOW = datetime(2026, 9, 24, 10, tzinfo=timezone.utc)

FUNBOOKER_PAGE = """
<meta property="og:image" content="https://res.cloudinary.com/funbooker/image/upload/ar_1:1,f_auto,q_auto,t_lr-medium,w_400/v1/marketplace-listing/abc"/>
<script type="application/ld+json">{"@graph":[{"@type":"Product","name":"D\\u00e9gustation de vin \\u00e0 Paris 10\\u00e8me","offers":{"@type":"AggregateOffer","lowPrice":54}}]}</script>
<a itemprop="item" href="/fr/category/gastronomie">
    <span itemprop="name">Activit&eacute;s gastronomiques</span>
<li class="mr-4 pb-2 font-weight-bold flex items-center">
  <i class="fal fun-icon fa-clock fa-lg mr-2" aria-hidden="true"></i> 1h30min </li>
<div id="map" data-text="49 Rue du Faubourg   du Temple, 75010 Paris, FR" data-lat="48.86" data-lng="2.36"></div>
"""


def test_funbooker_listing():
    url = "https://www.funbooker.com/fr/annonce/degustation-de-vin-a-paris-10eme/voir"
    activity = funbooker.normalize(funbooker.parse_listing(url, FUNBOOKER_PAGE)).activity
    assert (activity.title, activity.duration_minutes, activity.offers[0].price_min) == ("Dégustation de vin", 90, 54)
    assert (activity.venue.address, activity.venue.postal_code, activity.venue.latitude) == ("49 Rue du Faubourg du Temple", "75010", 48.86)
    assert str(activity.image.url).endswith("/image/upload/f_auto,q_auto,c_limit,w_1200/v1/marketplace-listing/abc")
    assert "gastronomie" in activity.categories
    assert funbooker._PARIS_LISTING.search(url)
    assert not funbooker._PARIS_LISTING.search("https://www.funbooker.com/fr/annonce/permis-cotier-a-lagny-sur-marne-77/voir")


PARIS_FRIENDLY_PAGE = """
<meta property="og:title" content="Atelier chocolat gratuit" />
<meta property="og:image" content="https://www.paris-friendly.fr/images/bons_plans_paris/14041/1.jpg" />
<ul>
  <li><div class="icon"><img src="/date@2x.png" alt="La date"></div>
      <p><strong>Date(s) et horaires</strong> : Les 16, 17 et 18 octobre 2026 - &agrave; r&eacute;server le 24 septembre &agrave; 14h</p></li>
  <li><div class="icon"><img src="/euro@2x.png" alt="Le tarif"></div><p>0 &euro;</p></li>
  <li><div class="icon"><img src="/bulle@2x.png" alt="Les informations"></div>
      <p><strong>Avec r&eacute;servation</strong> le 24 septembre &agrave; 14h : <a href="https://www.lvmh.com/masterclass">cliquez ici</a></p></li>
  <li><div class="icon"><img src="/location@2x.png" alt="Le lieu"></div>
      <div class="content"><p><strong><span itemprop="name">La Grande &Eacute;picerie</span></strong>,
      <span itemprop="address">38 rue de S&egrave;vres, 75007 Paris 75007 Paris</span></p>
      <p><a href="https://www.lagrandeepicerie.com/">site</a></p></div></li>
</ul>
"""


def test_paris_friendly_page_ignores_the_booking_date():
    payload = paris_friendly.parse_page(14041, "https://www.paris-friendly.fr/atelier.html", PARIS_FRIENDLY_PAGE)
    activity = paris_friendly.normalize(payload, NOW).activity
    assert (activity.starts_on, activity.ends_on) == (date(2026, 10, 16), date(2026, 10, 18))
    assert (activity.venue.name, activity.venue.address, activity.venue.postal_code) == ("La Grande Épicerie", "38 rue de Sèvres", "75007")
    assert activity.offers[0].is_free
    assert str(activity.website) == "https://www.lagrandeepicerie.com/"
    assert str(activity.offers[0].booking_url) == "https://www.lvmh.com/masterclass"
    no_venue = payload | {"address": None, "venue_name": None}
    assert paris_friendly.normalize(no_venue, NOW).rejection == "sans lieu"


PARIS_CITY_GAME_PAGE = """
<h3>Le Karaok&eacute; nouvelle g&eacute;n&eacute;ration</h3>
<div class="et_pb_gallery_image landscape"><a href="#"><img src="data:image/svg+xml,x" data-lazy-src="https://pariscitygame.fr/wp-content/uploads/2026/03/chante.jpg" /></a></div>
<div class="et_pb_module et_pb_blurb et_pb_blurb_0"><h6 class="et_pb_module_header">Activit&eacute; insolite</h6></div>
<div class="et_pb_module et_pb_blurb et_pb_blurb_3"><div class="et_pb_blurb_description">50 rue de Charenton, 75012 Paris</div></div>
<div class="et_pb_module et_pb_blurb et_pb_blurb_5"><div class="et_pb_blurb_description"><a href="https://chante.club/reserver/">R&eacute;server</a></div></div>
<div class="et_pb_module et_pb_blurb et_pb_blurb_6"><div class="et_pb_blurb_description">&agrave; partir de 29&euro;/personne</div></div>
<div class="et_pb_module et_pb_blurb et_pb_blurb_8"><div class="et_pb_blurb_description"><a href="https://www.instagram.com/chante_club/">Instagram</a></div></div>
"""


def test_paris_city_game_project():
    project = {"id": 19274, "slug": "chante", "link": "https://pariscitygame.fr/project/chante/", "title": {"rendered": "Chante!"}}
    activity = paris_city_game.normalize(paris_city_game.parse_project(project, PARIS_CITY_GAME_PAGE)).activity
    assert (activity.venue.address, activity.venue.postal_code, activity.offers[0].price_min) == ("50 rue de Charenton", "75012", 29)
    assert str(activity.website) == "https://chante.club/reserver/"
    assert str(activity.offers[0].booking_url) == "https://chante.club/reserver/"
    page = PARIS_CITY_GAME_PAGE.replace("https://chante.club/reserver/", "https://www.urbexscape.paris")
    urbex = paris_city_game.normalize(paris_city_game.parse_project(project, page)).activity
    assert str(urbex.offers[0].booking_url) == "https://www.urbexscape.paris/"
    assert str(activity.image.url) == "https://pariscitygame.fr/wp-content/uploads/2026/03/chante.jpg"
    assert activity.categories == ["jeux"]
