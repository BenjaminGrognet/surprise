from datetime import date, datetime, timezone

import httpx

from surprise.booking import engine_in
from surprise.collectors import dice, escape_game, osm_loisirs, privateaser, sortir_a_paris
from surprise.tags import tag

NOW = datetime(2026, 9, 26, 10, tzinfo=timezone.utc)

SORTIR_A_PARIS_PAGE = """
<meta property="og:image" content="https://cdn.sortiraparis.com/images/80/1462/1007226-bizz-art.jpg"/>
<script type="application/ld+json">{"@type":"NewsArticle","headline":"Les soirées du Bizz’Art : musique et fête au bord du canal","description":"Un club au bord de l'eau."}</script>
<div class="col-xs-12 col-md-6" id="practical-info">
  <div class="heading-reversed">Informations pratiques</div>
  <meta itemprop="startDate" content="2026-09-26T00:00:00+02:00"/>
  <meta itemprop="endDate" content="2027-12-30T00:00:00+01:00"/>
  <p><strong>Dates et Horaires</strong><br/><span>Samedi :</span> <span> de 20h à 3h </span></p>
  <p class="location-info"><strong>Lieu</strong><br/>
    <span itemprop="location" itemscope itemtype="http://schema.org/Place">
      <a itemprop="url" href="https://www.sortiraparis.com/lieux/53357-bizz-art-club"><span itemprop="name">Bizz&#039;Art Club</span></a><br/>
      <span itemprop="address" itemscope itemtype="http://schema.org/PostalAddress">
        <span itemprop="streetAddress">167 Quai de Valmy</span><br/>
        <span itemprop="postalCode">75010</span> <span itemprop="addressLocality">Paris 10</span>
      </span>
    </span><br/></p>
  <p><strong>Tarifs</strong><br/>Entrée : 15€</p>
  <p><strong>Site officiel</strong><br/><a href="https://bizzartclub.com/?utm_source=sortiraparis" target="_blank">bizzartclub.com</a></p>
  <p><strong>Réservations</strong><br/><a href="https://shotgun.live/fr/venues/bizz-art" target="_blank">shotgun.live</a><br/></p>
  <p><strong>Plus d&#039;informations</strong><br/>Durée : 1h30<br />Vestiaire gratuit</p>
</div>
<div class="col-xs-12 col-md-6"><div id="map-canvas" class="fake-map"></div>
<script>_mapHandler.init({"keyword":"default","id":"map-canvas","markers":[{"l":48.879194,"L":2.36639,"t":"Bizz'Art Club"}]});</script></div>
"""


def test_sortir_a_paris_practical_block():
    url = "https://www.sortiraparis.com/soiree/articles/306503-les-soirees-du-bizz-art"
    payload = sortir_a_paris.parse_article(url, SORTIR_A_PARIS_PAGE)
    assert (payload["article_id"], payload["section"]) == ("306503", "soiree")
    assert payload["name"] == "Les soirées du Bizz'Art : musique et fête au bord du canal"
    assert (payload["latitude"], payload["price_min"], payload["free"]) == (48.879194, 15.0, False)
    assert payload["website"] == "https://bizzartclub.com/"
    assert payload["booking_url"] == "https://shotgun.live/fr/venues/bizz-art"
    activity = sortir_a_paris.normalize(payload, NOW).activity
    assert (activity.venue.name, activity.venue.address, activity.venue.postal_code) == ("Bizz'Art Club", "167 Quai de Valmy", "75010")
    assert activity.is_evening and activity.starts_on == date(2026, 9, 26)
    assert "nuit" in activity.categories
    # An article about no place (a video game, a news item) is skipped.
    assert sortir_a_paris.parse_article(url, "<h1>Un jeu vidéo</h1>") is None
    assert sortir_a_paris._in_scope("https://www.sortiraparis.com/loisirs/insolite/articles/352008-tournage")
    assert not sortir_a_paris._in_scope("https://www.sortiraparis.com/soiree/guides/54875-les-soirees-du-week-end")
    assert not sortir_a_paris._in_scope("https://www.sortiraparis.com/loisirs/cinema/articles/1-un-film")


def test_sortir_a_paris_duration_is_no_opening_hour():
    page = SORTIR_A_PARIS_PAGE.replace("<span> de 20h à 3h </span>", "Tous les jours")
    payload = sortir_a_paris.parse_article("https://www.sortiraparis.com/loisirs/gaming/articles/1-x", page)
    assert payload["evening"] is None


def test_sortir_a_paris_run_ended_by_its_hours():
    # No dates marked up, "until" in the hours: a run that ended, not a permanent place.
    payload = sortir_a_paris.parse_article("https://www.sortiraparis.com/soiree/articles/1-x", SORTIR_A_PARIS_PAGE)
    payload |= {"starts_on": None, "ends_on": None, "hours": "Chaque jeudi et vendredi jusqu'au 25 septembre"}
    assert "passé" in sortir_a_paris.normalize(payload, NOW).rejection
    later = sortir_a_paris.normalize(payload | {"hours": "Chaque jeudi jusqu'au 30 octobre"}, NOW).activity
    assert later.kind == "temporary" and str(later.ends_on) == "2026-10-30"


# A guide's entries (one sponsored), among the links of its page: the menu, an article without data-id.
SORTIR_A_PARIS_GUIDE = """
<a href="/actualites/a-paris/articles/219977-meteo-a-paris">Météo</a>
<p><a href="/loisirs/gaming/articles/339094-breush-a-paris-action-painting" data-id="339094"><img src="x.jpg"/>
 <strong>Breush à Paris</strong></a><br/>Un cube immersif. <a href="/loisirs/gaming/articles/339094-breush-a-paris-action-painting">[Lire la suite]</a></p>
<p><a href="/arts-culture/balades/articles/153840-la-fury-room" data-counter="21:148968:153840:0" data-id="153840">
 <strong>La Fury Room</strong></a><br/>Sponsorisé - Se défouler.</p>
"""


def test_sortir_a_paris_reads_its_guides_for_a_band_first():
    """The articles its guides for a band of friends list come first, whatever their section or age, each once."""
    sitemap_index = '<sitemapindex><sitemap><loc>https://www.sortiraparis.com/sitemap-fr-1.xml</loc></sitemap></sitemapindex>'
    recent = "https://www.sortiraparis.com/soiree/articles/306503-les-soirees-du-bizz-art"
    breush = "https://www.sortiraparis.com/loisirs/gaming/articles/339094-breush-a-paris-action-painting"
    fury = "https://www.sortiraparis.com/arts-culture/balades/articles/153840-la-fury-room"  # a section not read otherwise
    sitemap_fr = f"<urlset><url><loc>{recent}</loc><lastmod>2026-09-20</lastmod></url><url><loc>{breush}</loc><lastmod>2026-09-21</lastmod></url></urlset>"

    def answer(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == sortir_a_paris.GUIDES[0]:
            return httpx.Response(200, text=SORTIR_A_PARIS_GUIDE)
        if "/guides/" in url:
            return httpx.Response(404)  # a guide that does not answer is skipped
        return httpx.Response(200, text=sitemap_index if url == sortir_a_paris.SITEMAP_INDEX else sitemap_fr)

    with httpx.Client(transport=httpx.MockTransport(answer)) as client:
        pages = list(sortir_a_paris.fetch_pages(client, NOW))
    assert pages == [breush, fury, recent]


DICE_PAGE = """
<script type="application/ld+json">{"@context":"https://schema.org","@type":"MusicEvent","name":"Less Drama More Techno",
"startDate":"2026-10-03T23:00:00+02:00","endDate":"2026-10-04T06:00:00+02:00",
"location":{"@type":"Place","name":"Le Chinois","address":{"@type":"PostalAddress","streetAddress":"6 Place de la Bastille, 75011 Paris, France"},
"geo":{"@type":"GeoCoordinates","latitude":48.853,"longitude":2.369}},
"image":["https://dice-media.imgix.net/attachments/x.jpg"],"description":"Techno all night.",
"offers":{"@type":"AggregateOffer","priceCurrency":"EUR","lowPrice":"12.00","highPrice":"18.00"}}</script>
"""


def test_dice_club_night():
    url = "https://dice.fm/event/abc123-less-drama-more-techno-3rd-oct-le-chinois-paris-tickets"
    payload = dice.parse_event(url, DICE_PAGE)
    assert payload["category_text"] == "soirée clubbing"
    activity = dice.normalize(payload, NOW).activity
    assert (activity.venue.name, activity.venue.address, activity.venue.postal_code) == ("Le Chinois", "6 Place de la Bastille", "75011")
    assert (float(activity.offers[0].price_min), float(activity.offers[0].price_max)) == (12, 18)
    assert str(activity.offers[0].booking_url) == url
    # The night ends the next day: its start is its session.
    assert [o.starts_at.hour for o in activity.occurrences] == [23] and activity.is_evening
    assert "nuit" in activity.categories


def test_dice_events_of_paris_by_the_day_in_their_address():
    today = date(2026, 9, 26)
    match = dice._PARIS_EVENT.match("https://dice.fm/event/eowlyy-dews-pegahorn-23rd-oct-nouveau-casino-paris-tickets")
    assert dice._day(match, today) == date(2026, 10, 23)
    # A day of January is next year's.
    match = dice._PARIS_EVENT.match("https://dice.fm/event/x1-show-2nd-jan-la-cigale-paris-tickets")
    assert dice._day(match, today) == date(2027, 1, 2)
    assert not dice._PARIS_EVENT.match("https://dice.fm/event/x2-show-2nd-jan-fabric-london-tickets")


ESCAPE_ROOM_PAGE = """
<article itemscope itemtype="http://schema.org/Product">
<img src="https://escapegame.imgix.net/62/620b.jpg?auto=format&amp;w=1400" alt="Un crime" itemprop="image" class="hero-image"/>
<div class="card-activity-type type-escapegame">
    Escape game
</div>
<h1 itemprop="name">
      Un crime presque parfait
</h1>
<div class="col-md-8 col-lg-9" id="jsMainColumn">
<section class="room-abstract mb-4" id="review">
<meta itemprop="description" content="Un meurtre a eu lieu à la Lock Academy.">
<div class="row row-cols-auto g-2 room-specs">
  <div class="col"><div>
    Thème <br/><strong>Enquête</strong>
  </div></div>
  <div class="col"><div>
    Durée<br/><strong>60 min</strong>
  </div></div>
  <div class="col"><div>
    Nombre de joueurs <br/>
    <strong>2</strong> à <strong>5 joueurs</strong>
  </div></div>
  <div class="col"><div>
    Prix <br/><strong>27 à 55€</strong>/joueur
  </div></div>
  <div class="col"><div>
    Âge <br/>dès <strong>12 ans</strong>
  </div></div>
</div>
</section>
<div class="mt-4" id="avis"></div>
</div>
<div class="col-md-4 col-lg-3 top15-sm" id="resa">
<div id="jsBookingSection">
  <strong>Prochaines disponibilités</strong>
  <div id="jsAvailabilities" data-domain="https://availability.4escape.io/egfr/" data-room-id="lockacademy-paris/629d"></div>
  <div class="top15">
    <a href="https://lockacademy.com?source=escapegamefr&amp;utm_source=escapegamefr&amp;utm_medium=referral" class="button button-block jsOutBound">
      Voir tous les créneaux
    </a>
  </div>
  <div class="row g-3 room-location"><div class="col-9">
    <strong class="h4 bottom10">Lock Academy</strong>
    <a href="http://maps.google.com/?ll=48.8682244,2.3533099" target="blank" rel="nofollow" class="room-address" >131 Boulevard de Sébastopol, Paris, France</a>
    <a href="http://maps.google.com/?ll=48.8639473,2.3420492" target="blank" rel="nofollow" class="room-address" >25 Rue Coquillière, 75001 Paris, France</a>
  </div></div>
</div>
</div>
</article>
"""


def test_escape_game_room():
    url = "https://www.escapegame.fr/paris/lock-academy/crime-crapuleux-a-la-lock-academy/"
    payload = escape_game.parse_room(url, ESCAPE_ROOM_PAGE)
    assert payload["room"] == "lock-academy/crime-crapuleux-a-la-lock-academy"
    assert (payload["players_min"], payload["players_max"], payload["duration_minutes"]) == (2, 5, 60)
    assert (payload["price_min"], payload["price_max"]) == (27.0, 55.0)
    assert payload["booking_url"] == "https://lockacademy.com"
    assert payload["image_url"] == "https://escapegame.imgix.net/62/620b.jpg"
    # The company's first place in Paris with its postcode.
    assert (payload["address"], payload["latitude"]) == ("25 Rue Coquillière, 75001 Paris, France", "48.8639473")
    activity = escape_game.normalize(payload, NOW).activity
    assert activity.title == "Escape game : Un crime presque parfait"
    assert (activity.venue.name, activity.venue.address, activity.venue.postal_code) == ("Lock Academy", "25 Rue Coquillière", "75001")
    assert activity.duration_minutes == 60 and "jeux" in activity.categories
    # "dès 12 ans" is an age limit, not a children's show.
    assert "escape_game" in tag(activity.model_dump(mode="json"))


def test_escape_room_for_three_or_more_is_kept_for_a_band():
    page = ESCAPE_ROOM_PAGE.replace("<strong>2</strong> à <strong>5 joueurs</strong>", "<strong>4</strong> à <strong>8 joueurs</strong>")
    payload = escape_game.parse_room("https://www.escapegame.fr/paris/team-break/prison-break/", page)
    result = escape_game.normalize(payload, NOW)
    # A band's (Secret Squad), its number of players kept: a couple's evening never proposes it.
    assert result.rejection is None
    assert (result.activity.players_min, result.activity.players_max) == (4, 8)
    closed = ESCAPE_ROOM_PAGE.replace("</section>", "</section><p>Cette salle est définitivement fermée.</p>")
    payload = escape_game.parse_room("https://www.escapegame.fr/paris/lock-academy/x/", closed)
    assert escape_game.normalize(payload, NOW).rejection == "fermé définitivement"


def test_osm_leisure_venues_say_their_kind():
    climbing = {
        "type": "node", "id": 7, "lat": 48.83, "lon": 2.37, "kind": "climbing",
        "tags": {"sport": "climbing", "name": "Arkose Nation", "addr:postcode": "75012", "addr:street": "Rue de Picpus",
                 "addr:housenumber": "2", "website": "https://arkose.com/nation"},
    }
    site = {"engine": "Bookeo", "booking_url": "https://bookeo.com/arkose"}
    activity = osm_loisirs.normalize(osm_loisirs.facts(climbing, site), NOW).activity
    assert (activity.title, activity.venue.name, activity.venue.address) == ("Escalade : Arkose Nation", "Arkose Nation", "2 Rue de Picpus")
    assert "sensations" in activity.categories
    karaoke = climbing | {"kind": "karaoke", "tags": {"amenity": "karaoke_box", "name": "Karaoke Box Bastille", "addr:postcode": "75011"}}
    assert osm_loisirs.facts(karaoke, {})["name"] == "Karaoke Box Bastille"
    assert osm_loisirs.normalize(osm_loisirs.facts(karaoke, {}), NOW).rejection == "sans réservation en ligne"
    # A bar with games needs no booking: its games in the title.
    bar = climbing | {"kind": "bar_games", "tags": {
        "amenity": "bar", "sport": "darts;billiards;table_soccer", "name": "The Lions", "addr:postcode": "75011",
        "opening_hours": "Mo 11:00-00:00; Sa 19:00-02:00",
    }}
    payload = osm_loisirs.facts(bar, {})
    assert payload["name"] == "Fléchettes et billard : The Lions" and payload["evening"]
    activity = osm_loisirs.normalize(payload, NOW).activity
    assert "bar" in activity.categories and "jeu_actif" in tag(activity.model_dump(mode="json"))
    assert osm_loisirs.open_late("Mo-Fr 09:30-19:00") is False and osm_loisirs.open_late(None) is None
    # A name that says its kind keeps it ("Mad Golf" is no video game); table football alone makes no games bar.
    arcade = climbing | {"tags": {"leisure": "amusement_arcade", "name": "Mad Golf", "website": "https://madgolf.fr"}}
    assert osm_loisirs.facts(arcade, {})["name"] == "Mad Golf"
    assert osm_loisirs.kind_of({"amenity": "bar", "sport": "table_soccer"}) is None
    # "ping_pong" is no bowling.
    assert osm_loisirs.kind_of({"leisure": "sports_centre", "sport": "climbing;ping_pong"})[0] == "climbing"
    assert osm_loisirs.kind_of({"leisure": "sports_centre", "sport": "tennis"}) is None


PRIVATEASER_PAGE = """
<meta property="og:image" content="https://privateaser-media.s3.eu-west-1.amazonaws.com/etab_photos/1608/750x375/424234.jpg">
<div class="cover-title"> <h1 itemprop="name"> Le Capitole Caf&eacute; </h1> </div>
<div class="concept-labels"> <div class="concept-label bolder">Terrasse</div> <div class="concept-label bolder">Bar dansant</div> </div>
<span itemscope itemtype="https://schema.org/PostalAddress" itemprop="address"> 105 Boulevard de Sébastopol, 75002 Paris
  <meta itemprop="postalCode" content="75002"> <meta itemprop="streetAddress" content="105 Boulevard de Sébastopol"> </span>
<div itemprop="geo" itemscope itemtype="https://schema.org/GeoCoordinates">
  <meta itemprop="latitude" content="48.866448"> <meta itemprop="longitude" content="2.352206"> </div>
<meta itemprop="openingHours" content="Mo-We 07:30-01:00"> <meta itemprop="openingHours" content="Su 08:00-17:00">
<div itemprop="description"> <div class="offering-seo-description truncate-overflow">
  <p>Une grande terrasse, des DJ sets le jeudi.</p> <p>Des espaces privatisables pour vos anniversaires.</p> </div> Lire plus </div>
<div class="booking-option-card__content"> <div class="title-block"> <h3 class="title">Réserver quelques tables</h3>
  <div class="capacity-block"> 1-440 personnes </div></div></div>
<div class="booking-option-card__content"> <div class="title-block"> <h3 class="title">Privatiser l'établissement entier</h3>
  <div class="capacity-block"> 80-200 personnes </div></div></div>
"""


def test_privateaser_bar_booked_for_a_group():
    url = "https://www.privateaser.com/lieu/1608-le-capitole-cafe"
    payload = privateaser.parse_venue(url, PRIVATEASER_PAGE)
    assert (payload["venue_id"], payload["name"], payload["postal_code"]) == ("1608", "Le Capitole Café", "75002")
    assert payload["lead_text"] == "Une grande terrasse, des DJ sets le jeudi.\nDes espaces privatisables pour vos anniversaires."
    # A few tables for one to 440, the whole bar for 80 to 200: any party from one to 440.
    assert (payload["players_min"], payload["players_max"]) == (1, 440)
    activity = privateaser.normalize(payload, NOW).activity
    assert (activity.venue.address, activity.venue.latitude, activity.is_evening) == ("105 Boulevard de Sébastopol", 48.866448, True)
    assert "bar" in activity.categories
    offer = activity.offers[0]
    assert (str(offer.booking_url), offer.online_booking, offer.paid_booking) == (url, True, False)
    assert engine_in(url) == "Privateaser"
    assert privateaser.parse_venue(url, "<h2>Page introuvable</h2>") is None


def test_privateaser_open_in_the_evening():
    assert privateaser.is_evening(["Mo-We 07:30-01:00"])  # past midnight
    assert privateaser.is_evening(["Tu-Sa 17:00-23:30"])
    assert not privateaser.is_evening(["Mo-Fr 08:00-17:00", "Su 10:00-19:00"])


def test_privateaser_bars_come_page_after_page_until_one_adds_none():
    bar = '<a href="https://www.privateaser.com/lieu/{0}-bar-{0}">Bar</a>'
    pages = {"1": bar.format(1) + bar.format(2), "2": bar.format(2) + bar.format(3), "3": bar.format(3)}

    def answer(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(privateaser.LISTING)
        return httpx.Response(200, text=pages.get(request.url.params["page"], ""))

    with httpx.Client(transport=httpx.MockTransport(answer)) as client:
        urls = list(privateaser.venue_urls(client, delay=0))
    assert urls == [f"https://www.privateaser.com/lieu/{n}-bar-{n}" for n in (1, 2, 3)]


def test_privateaser_stops_when_the_site_blocks_it():
    """Its CloudFront answers 403 to a robot reading too fast: a few pages in a row unanswered end the run."""
    asked = []

    def answer(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(privateaser.LISTING):
            bars = "".join(f'<a href="https://www.privateaser.com/lieu/{n}-bar">Bar</a>' for n in range(1, 9))
            return httpx.Response(200, text=bars if request.url.params["page"] == "1" else "")
        asked.append(str(request.url))
        return httpx.Response(403, text="Request blocked.")

    with httpx.Client(transport=httpx.MockTransport(answer)) as client:
        assert list(privateaser.collect(client, NOW, delay=0)) == []
    assert len(asked) == privateaser.BLOCKED_AFTER
