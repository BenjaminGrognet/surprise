from surprise import keywords
from surprise.originality import Scorer


def item(title, categories=(), source_id="funbooker", lead_text=None, venue="Lieu", kind="permanent"):
    return {
        "source_id": source_id,
        "external_id": title,
        "lead_text": lead_text,
        "activity": {"title": title, "categories": list(categories), "kind": kind, "venue": {"name": venue}},
        "enrichment": {},
    }


def test_keywords_read_every_text():
    found = keywords.extract("Un bar secret derrière une porte dérobée, cocktails signature aux chandelles, vue sur la Seine")
    assert {"secret", "cocktails", "aux chandelles", "vue panoramique"} <= set(found)
    assert "secret" not in keywords.extract("Découvrez les secrets de la pâtisserie")
    assert keywords.texts(item("Titre", lead_text="Texte")) == "Titre Lieu Texte"


def test_offbeat_curated_rare_beats_a_tourist_classic():
    base = [item(f"Stand-up {n}", ["humour"]) for n in range(50)]
    hidden = item("Bar caché : speakeasy derrière une laverie", ["bar", "lieu_insolite"], source_id="paris_zigzag", lead_text="Une adresse insolite")
    classic = item("Croisière Bateaux-Mouches et Tour Eiffel", ["croisiere"], source_id="getyourguide")
    scorer = Scorer(base + [hidden, classic])
    offbeat, tourist, common = scorer.score(hidden), scorer.score(classic), scorer.score(base[0])
    assert offbeat.score > common.score > tourist.score
    assert "repéré par un média de curation" in offbeat.reasons and "classique touristique" in tourist.reasons
    assert 0 <= tourist.score and offbeat.score <= 100


def test_chains_only_count_for_places_to_eat():
    scorer = Scorer([])
    tour = item("Visite de Montmartre", ["visite"], venue="Devant le restaurant Five Guys, métro Blanche")
    burger = item("Five Guys Opéra", ["restaurant"])
    assert "chaîne" not in scorer.score(tour).reasons and "chaîne" in scorer.score(burger).reasons


def test_an_outing_out_of_the_ordinary_by_nature():
    # An escape game is not done every week: by what it is, well above a restaurant, without any text saying so.
    scorer = Scorer([])
    escape, restaurant = scorer.score(item("Escape game : Mission Mars", ["jeux"])), scorer.score(item("Chez Léa", ["restaurant"]))
    assert escape.score >= 55 and restaurant.score <= 35
    assert "hors du quotidien : escape game" in escape.reasons
    # A restaurant named after a workshop's tag ("La Cuisine de…") is no cooking class.
    assert not [r for r in scorer.score(item("La Cuisine de Léa", ["restaurant"])).reasons if r.startswith("hors du quotidien")]


def test_texts_tell_what_an_evening_there_holds():
    # A bar's name says nothing; the media's text says karaoke, blind tests and performers.
    text = "Bar-restaurant festif : karaoké endiablé, blind-tests, performeurs, un décor immersif."
    bar = Scorer([]).score(item("Casa Loca", ["bar"], source_id="selections_squad", lead_text=text))
    plain = Scorer([]).score(item("Casa Loca", ["bar"], source_id="privateaser", lead_text="Un bar à cocktails."))
    assert bar.score >= 70 and plain.score <= 35
    assert any(r.startswith("hors du quotidien : karaoke") for r in bar.reasons) and "repéré par un média de curation" in bar.reasons
    # A quiz said in the title and the text counts once.
    quiz = Scorer([]).score(item("Quiz game", ["jeux"], lead_text="Un quiz entre amis"))
    assert quiz.reasons[0] == "hors du quotidien : quiz"


def test_a_themed_night_in_a_castle():
    scorer = Scorer([])
    night = scorer.score(item("Soirée Halloween au Château de Vincennes", ["concert"], lead_text="Château entièrement décoré, concert et animations."))
    visit = scorer.score(item("Visite du Château de Vincennes", ["visite"]))
    play = scorer.score(item("Un Château de Cartes", ["theatre"]))
    assert night.score > visit.score > play.score
    assert night.score >= 55 and "château, manoir" not in " ".join(play.reasons)
