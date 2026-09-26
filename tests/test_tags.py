import pytest

from surprise.categories import categorize
from surprise.tags import TAGS, VIBES, describe, tag


def activity(title, venue=None, categories=()):
    return {"title": title, "venue": {"name": venue} if venue else None, "categories": list(categories)}


@pytest.mark.parametrize(
    ("title", "venue", "categories", "tags", "vibes"),
    [
        ("Mad Golf", None, [], {"mini_golf"}, {"bouger", "defi"}),
        ("Escape Game \"The Greenhouse\"", None, ["jeux"], {"escape_game"}, {"defi"}),
        ("Massages en duo", None, ["bien_etre"], {"massage", "en_duo"}, {"detente", "romantique"}),
        ("Candlelight : hommage à Adele", "Maison de l'Océan", [], {"classique", "chandelles"}, {"musique", "emerveiller", "romantique"}),
        ("Catacombes de Paris : Billet d'entrée + Audioguide", None, ["lieu_insolite"], {"souterrain", "frisson"}, {"frisson", "insolite"}),
        ("Atelier tournage & peinture sur céramique en duo", None, ["atelier"], {"ceramique", "peinture_dessin"}, {"creer"}),
        ("Hôtel Erotica : un spectacle érotique", None, ["theatre"], {"coquin"}, {"coquin"}),
        ("Secret Square : spectacles de strip-tease", None, ["cabaret"], {"coquin", "cabaret"}, {"coquin", "emerveiller"}),
        ("Action game : Push", "Active Room", ["jeux"], {"jeu_actif"}, {"bouger", "defi"}),
        ("Fléchettes et baby-foot : The Lions", "The Lions", ["bar"], {"jeu_actif"}, {"bouger"}),
        ("Réalité virtuelle : Time Travel : Chapter 1", "Virtual Room", ["sensations"], {"jeu_video"}, {"defi"}),
        ("Soirée pin-up et swing", None, [], {"coquin", "danse"}, {"coquin"}),
    ],
)
def test_tags_and_vibes(title, venue, categories, tags, vibes):
    found = describe(activity(title, venue, categories))
    assert tags <= set(found["tags"])
    assert vibes <= set(found["vibes"])


@pytest.mark.parametrize(
    ("title", "venue", "absent"),
    [
        ("Billets pour Disneyland® Paris + Transport en RER", None, "sport"),  # "sport" inside "transport"
        ("Tragedy Club – Murder Party Paris", None, "electro"),
        ("Atelier Madeleine", None, "eglise"),
        ("Bruges : Excursion autoguidée au départ de Paris", None, "art"),  # "art" inside "départ"
        ("Hello Kitty : Beyond Cute - Paris", "Galerie Joseph", "frisson"),
        ("Dj Krush + Guest", "La Machine du Moulin Rouge", "cabaret"),
        ("Bérengère Krief dans Sexe", "L'Olympia", "coquin"),
        ("Strip", "Théâtre de la Cité Internationale", "coquin"),
        ("Libertino", None, "coquin"),
        ("La Tropicana - Sex Intention - Dj Yoyow", None, "coquin"),
        ("Réalité virtuelle : Time Travel : Chapter 1", "Virtual Room", "classique"),  # "ravel" inside "travel"
        ("Escape game : Anatole Latuile : opération Morvox d'or", None, "classique"),
    ],
)
def test_rules_avoid_false_matches(title, venue, absent):
    assert absent not in tag(activity(title, venue))


def test_category_implies_tag_when_the_title_says_little():
    assert "sur_l_eau" in tag(activity("Péniche River's King", categories=["croisiere"]))
    assert "spa" in tag(activity("Le Sevrien", categories=["bien_etre"]))


def test_every_tag_leads_to_a_vibe_or_describes_a_setting():
    used = set().union(*(vibe["tags"] for vibe in VIBES.values()))
    orphans = {key for key, info in TAGS.items() if key not in used and info["facet"] == "activite"}
    assert orphans == set()


def test_categories_avoid_false_matches():
    assert "concert" not in categorize("Escape game : Anatole Latuile : opération Morvox d'or")
    assert "danse" not in categorize("Escape game : Cannibal Island")
    assert "danse" in categorize("Grand bal swing")


def test_a_driving_simulator_is_not_on_the_water():
    assert "sur_l_eau" not in describe({"title": "Sim Drivers", "categories": []})["tags"]
    assert "sur_l_eau" in describe({"title": "River Café", "categories": []})["tags"]
