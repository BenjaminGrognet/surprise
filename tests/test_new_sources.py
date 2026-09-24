from datetime import date, datetime, timezone

from surprise.collectors import come_to_paris, funbooker, paris_city_game, paris_friendly, paris_secret

NOW = datetime(2026, 9, 24, 10, tzinfo=timezone.utc)

FUNBOOKER_PAGE = """
<meta property="og:image" content="https://res.cloudinary.com/funbooker/image/upload/ar_1:1,f_auto,q_auto,t_lr-medium,w_400/v1/marketplace-listing/abc"/>
<script type="application/ld+json">{"@graph":[{"@type":"Product","name":"D\\u00e9gustation de vin \\u00e0 Paris 10\\u00e8me","offers":{"@type":"AggregateOffer","lowPrice":54},"description":"<p>Trois vins &agrave; d&eacute;guster.</p><ul><li>Rouge</li><li>Blanc</li></ul>"}]}</script>
<a itemprop="item" href="/fr/category/gastronomie">
    <span itemprop="name">Activit&eacute;s gastronomiques</span>
<li class="mr-4 pb-2 font-weight-bold flex items-center">
  <i class="fal fun-icon fa-clock fa-lg mr-2" aria-hidden="true"></i> 1h30min </li>
<div id="map" data-text="49 Rue du Faubourg   du Temple, 75010 Paris, FR" data-lat="48.86" data-lng="2.36"></div>
"""


def test_funbooker_listing():
    url = "https://www.funbooker.com/fr/annonce/degustation-de-vin-a-paris-10eme/voir"
    payload = funbooker.parse_listing(url, FUNBOOKER_PAGE)
    assert payload["lead_text"] == "Trois vins à déguster.\nRouge\nBlanc"
    activity = funbooker.normalize(payload).activity
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
<div class="title"><time itemprop="startDate" datetime="2026-10-16"> </time></div>
<div class="content"><p>Un atelier <strong>chocolat</strong>.<h2>Au programme</h2>D&eacute;gustation.</p></div>
"""


def test_paris_friendly_page_ignores_the_booking_date():
    payload = paris_friendly.parse_page(14041, "https://www.paris-friendly.fr/atelier.html", PARIS_FRIENDLY_PAGE)
    activity = paris_friendly.normalize(payload, NOW).activity
    assert (activity.starts_on, activity.ends_on) == (date(2026, 10, 16), date(2026, 10, 18))
    assert (activity.venue.name, activity.venue.address, activity.venue.postal_code) == ("La Grande Épicerie", "38 rue de Sèvres", "75007")
    assert activity.offers[0].is_free
    assert str(activity.website) == "https://www.lagrandeepicerie.com/"
    assert str(activity.offers[0].booking_url) == "https://www.lvmh.com/masterclass"
    assert payload["lead_text"] == "Un atelier chocolat.\nAu programme\nDégustation."
    no_venue = payload | {"address": None, "venue_name": None}
    assert paris_friendly.normalize(no_venue, NOW).rejection == "sans lieu"
    assert paris_friendly.normalize(payload | {"venue_name": "Paris"}, NOW).rejection == "lieu imprécis"
    hydrafacial = payload | {"title": "Hydrafacial : un soin visage chez Skincare Agency"}
    assert paris_friendly.normalize(hydrafacial, NOW).rejection == "hors sujet"


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


COME_TO_PARIS_PAGE = """
<script type="application/ld+json">{"@type":"BreadcrumbList","itemListElement":[{"name":"Come to Paris"},{"name":"Croisières"},{"name":"Dîner"}]}</script>
<script type="application/ld+json">{"@type":"Product","@id":"#p","description":"Court.","offers":{"lowPrice":"89.00","highPrice":129},
"image":[{"@type":"ImageObject","contentUrl":"https://www.cometoparis.com/data/diner.1000w.jpg"}]}</script>
<script type="application/ld+json">{"@type":"Product","@id":"#p","name":"Dîner croisière sur la Seine"}</script>
<section id="product_practical_info"><h2 class="section_title">Ce qui vous attend</h2>
<p>Un dîner &agrave; bord.</p><h3>Horaires</h3><div>Tous les jours : 20h30</div><h3>Tarifs</h3><h2>FAQ</h2></section>
<div class="title">Adresse</div><div class="map_key"><div class="float_left w6of7"> Port de la Bourdonnais<br>75007 Paris </div></div>
<div id="google_map_box" data-latitude="48.86" data-longitude="2.29"></div>
"""


def test_come_to_paris_product():
    url = "https://www.cometoparis.com/fre/diner-croisiere-paris/diner-seine-m9000670"
    payload = come_to_paris.parse_product(url, COME_TO_PARIS_PAGE)
    assert payload["lead_text"] == "Un dîner à bord.\nHoraires\nTous les jours : 20h30\nTarifs"
    result = come_to_paris.normalize(payload)
    activity = result.activity
    assert result.raw.external_id == "9000670"
    assert (activity.title, activity.venue.address, activity.venue.postal_code, activity.venue.latitude) == (
        "Dîner croisière sur la Seine", "Port de la Bourdonnais", "75007", 48.86)
    assert (activity.offers[0].price_min, activity.offers[0].price_max) == (89, 129)
    assert activity.is_evening is True
    assert str(activity.image.url) == "https://www.cometoparis.com/data/diner.1000w.jpg"


PARIS_SECRET_PAGE = """
<article class="post-single"><h1 class="single__title">Hilary Duff au Z&eacute;nith : l&rsquo;ic&ocirc;ne en tourn&eacute;e</h1>
<p>Un concert tr&egrave;s attendu.</p>
<h3>Informations pratiques</h3>
<p><strong>Date</strong> : Vendredi 9 octobre 2026 &agrave; 20h<br><strong>Lieu</strong> : Z&eacute;nith Paris, 211 avenue Jean Jaur&egrave;s, 75019 Paris</p>
<p>Une expo en data design.</p>
<div class="fever-plan full-view" data-fever-plan-id="716002" data-fever-plan-name="FINALLY, SOMETHING GOOD" data-fever-plan-price="5"
 data-fever-plan-date="2026-10-15 11:00:00" data-fever-plan-brand="3 bis, rue Papin, 75003">
<img src="https://applications-media.feverup.com/plan.jpg"><p class="fever-plan__date">15 octobre 2026 11:00 + davantage de dates disponibles</p>
<a class="fever-plan__location-link" href="https://feverup.com/m/716002#plan-location">La Ga&icirc;t&eacute; Lyrique</a>
<div class="fever-plan__cta"></div></div>
</article>
"""


def test_paris_secret_practical_block_and_fever_card():
    url = "https://parissecret.com/hilary-duff-concert/"
    concert, expo = (paris_secret.normalize(p, NOW) for p in paris_secret.parse_article(url, PARIS_SECRET_PAGE))
    assert concert.raw.external_id == "hilary-duff-concert#hilary-duff-au-zenith"
    assert concert.raw.payload["lead_text"] == "Un concert très attendu."
    assert (concert.activity.title, concert.activity.venue.name, concert.activity.starts_on) == (
        "Hilary Duff au Zénith", "Zénith Paris", date(2026, 10, 9))
    assert concert.activity.is_evening is True
    assert expo.raw.external_id == "fever-716002"
    assert expo.raw.payload["lead_text"] == "Une expo en data design."
    activity = expo.activity
    assert (activity.venue.name, activity.venue.address, activity.venue.postal_code) == ("La Gaîté Lyrique", "3 bis, rue Papin", "75003")
    assert (activity.starts_on, activity.offers[0].price_min, activity.is_evening) == (date(2026, 10, 15), 5, False)
    assert str(activity.offers[0].booking_url) == "https://feverup.com/m/716002"
