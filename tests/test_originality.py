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
