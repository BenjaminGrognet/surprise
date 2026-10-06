"""Evenings composed through the API from real activities of the base (tests/fixtures/catalogue.json): for each
wish, several routes whose every step has its photo and its own text; and the couple's whole journey (test_journey)
on them."""

from datetime import date, timedelta

import pytest

import real_catalogue
import snapshot_catalogue
from test_journey import _chains, api, test_a_couple_composes_changes_and_keeps_an_evening, test_a_route_is_drawn_again_without_its_activities  # noqa: F401
from test_parcours import DAY
from test_quiz import ANSWERS

assert snapshot_catalogue.DAY == DAY  # test_journey asks for that day


@pytest.fixture
def base():
    return real_catalogue.base()


def test_the_dates_move_by_whole_weeks():
    later = DAY + timedelta(weeks=4)
    sessions = lambda items: [o["starts_at"] for i in items for o in i["activity"]["occurrences"]]  # noqa: E731
    before, after = sessions(real_catalogue.items()), sessions(real_catalogue.items(later))
    assert before and all(date.fromisoformat(b[:10]) + timedelta(weeks=4) == date.fromisoformat(a[:10]) for b, a in zip(before, after))
    with pytest.raises(AssertionError):
        real_catalogue.items(later + timedelta(days=1))


def test_a_play_of_the_base_named_after_a_dinner_is_never_the_evenings_dinner(api):
    # "Dîner De Famille", a play at the Café de la Gare: its title named a meal, the clues promised a table.
    play = next(i for i in real_catalogue.items() if i["activity"]["title"] == "Dîner De Famille")
    assert "theatre" in play["activity"]["categories"]
    page = api("/api/soirees", {"envies": ["rire"], "diner": True, "day": DAY.isoformat()})
    steps = [step for route in page["routes"] for step in route["steps"]]
    assert steps
    for step in steps:
        if step["title"] == "Dîner De Famille":
            assert step["role"] == "sortie" and "savourer" not in step["vibes"], step


@pytest.mark.parametrize("profiled", [True, False], ids=["profil", "sans profil"])
@pytest.mark.parametrize("envies, diner", snapshot_catalogue.WISHES, ids=lambda value: str(value))
def test_each_wish_gets_routes_shown_whole(api, envies, diner, profiled):
    evening = {"envies": envies, "diner": diner, "day": DAY.isoformat()}
    if profiled:
        evening["profile"] = api("/api/profiles", {"answers": ANSWERS})["profile"]
    page = api("/api/soirees", evening)
    assert len(page["routes"]) > 1, page
    for route in page["routes"]:
        _chains(route)
        assert route["title"] and route["secret_title"]
        for step in route["steps"]:
            assert step["title"] and step["text"] and step["image_url"].startswith(("https://", "http://")), step


@pytest.mark.parametrize("envies, occasion", [(["bande"], None), (["trinquer", "rire"], "evjf"), (["fete"], "anniversaire")], ids=str)
def test_a_band_gets_routes_shown_whole(api, envies, occasion):
    # Secret Squad on the real activities: eight friends, routes to share, every price counting them all.
    page = api("/api/soirees", {"formule": "squad", "personnes": 8, "envies": envies, "occasion": occasion, "diner": False, "day": DAY.isoformat()})
    assert page["personnes"] == 8 and len(page["routes"]) > 1, page
    for route in page["routes"]:
        _chains(route)
        assert route["title"] and route["secret_title"] and "par personne" in route["pitch"]
        for step in route["steps"]:
            assert step["title"] and step["text"] and step["image_url"].startswith(("https://", "http://")), step
            assert "duo" not in step["title"].lower(), step
