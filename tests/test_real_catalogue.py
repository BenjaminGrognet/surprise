"""Evenings composed through the API from the activities of the project's base (tests/prod_activities.py: read in
production, never written), for the next Friday as the app proposes it: for each wish, several routes that chain, each
step with its own text; a band's evenings; and a couple's journey, a step changed, a route drawn again, one kept and the
next evening without it. Everything the API writes stays in the test's own store; no booking engine is asked."""

import random
from datetime import datetime, time, timedelta

import pytest

import prod_activities
from surprise import images, parcours, quiz
from test_journey import _chains, _keys, api  # noqa: F401 (the fixture)
from test_quiz import ANSWERS

DAY = prod_activities.next_friday()
# The photo filters as production has them, whatever the other tests set (conftest): a step may then show the app's
# picture of its kind.
PRODUCTION_FILTERS = parcours.IMAGE_FILTERS
# Each wish once (an evening takes a couple of seconds on the whole base), with the couple's profile or without in turn.
WISHES = [
    (["rire"], False, True), (["rire"], True, False), (["romantique"], True, True),
    (["jouer"], False, False), (["musique"], False, True), (["fete"], False, False),
]


@pytest.fixture(scope="session")
def prod_base():
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(parcours, "IMAGE_FILTERS", PRODUCTION_FILTERS)
        try:
            return prod_activities.base()
        except LookupError as error:
            pytest.skip(str(error))


@pytest.fixture
def base(prod_base, monkeypatch):
    """The activities the server composes from: production's, with its photo filters; no image downloaded here (a
    site that forbids showing its images elsewhere: the step shows the app's picture)."""
    monkeypatch.setattr(parcours, "IMAGE_FILTERS", PRODUCTION_FILTERS)
    monkeypatch.setattr(images, "local_copy", lambda url, client=None, directory=None: None)
    return prod_base


def _shown_whole(page):
    assert len(page["routes"]) > 1, page
    for route in page["routes"]:
        _chains(route)
        assert route["title"] and route["secret_title"]
        for step in route["steps"]:
            # Its own text; the site's photo, or none (the app's picture).
            assert step["title"] and step["text"], step
            assert step["image_url"] is None or step["image_url"].startswith(("https://", "http://", "/images/")), step


@pytest.mark.parametrize("envies, diner, profiled", WISHES, ids=str)
def test_each_wish_gets_routes_shown_whole(api, envies, diner, profiled):
    evening = {"envies": envies, "diner": diner, "day": DAY.isoformat()}
    if profiled:
        evening["profile"] = api("/api/profiles", {"answers": ANSWERS})["profile"]
    _shown_whole(api("/api/soirees", evening))


@pytest.mark.parametrize("envies, occasion", [(["trinquer", "rire"], "evjf"), (["surprise"], "anniversaire")], ids=str)
def test_a_band_gets_routes_shown_whole(api, envies, occasion):
    # Secret Squad: eight friends, routes to share, every price counting them all.
    page = api("/api/soirees", {"formule": "squad", "personnes": 8, "envies": envies, "occasion": occasion, "diner": False, "day": DAY.isoformat()})
    assert page["personnes"] == 8
    _shown_whole(page)
    for route in page["routes"]:
        assert "par personne" in route["pitch"]
        assert all("duo" not in step["title"].lower() for step in route["steps"]), route


def test_a_couple_changes_a_step_redraws_a_route_and_keeps_the_evening(api):
    # The same draw of luck (parcours.lucky) each run: a route redrawn is all new when the base has one, but the draw
    # decides which candidates are looked at first, and the production base changes every night.
    random.seed(2026)
    profile = api("/api/profiles", {"answers": ANSWERS})["profile"]
    evening = {"envies": ["rire", "jouer"], "diner": False, "day": DAY.isoformat(), "profile": profile}
    page = api("/api/soirees", evening)
    name = page["name"]
    shown = {key for route in _keys(page) for key in route}
    assert sum(map(len, _keys(page))) == len(shown)  # no activity in two routes

    # The last step changed, three times: never an activity the page had.
    last = len(page["routes"][0]["steps"]) - 1
    for _ in range(3):
        page = api(f"/api/parcours/{name}/routes/0/steps/{last}", {})
        assert not isinstance(page, tuple), page
        new = page["routes"][0]["steps"][last]["id"]
        assert new not in shown
        shown.add(new)
        _chains(page["routes"][0])

    # Another route in place of the second, with none of the activities already shown.
    redrawn = api(f"/api/parcours/{name}/routes/1", {})
    assert not isinstance(redrawn, tuple), redrawn
    assert not set(_keys(redrawn)[1]) & shown
    _chains(redrawn["routes"][1])

    # Kept: the page's only route; the next evening, its history given, never proposes what was kept.
    kept = redrawn["routes"][0]
    page = api(f"/api/parcours/{name}/routes/0/choose", {})
    assert page["chosen"] and [step["id"] for step in page["routes"][0]["steps"]] == [step["id"] for step in kept["steps"]]
    following = api("/api/soirees", {**evening, "done": [name]})
    assert not {step["id"] for step in kept["steps"]} & {key for route in _keys(following) for key in route}


def test_an_evening_moved_to_another_day_keeps_its_steps_where_it_can_and_draws_the_others_again(api):
    # An evening ready (composed by the server for a date that counts, or by the form), moved a week on: a new page,
    # each step at the same hour if it can be that day, the others drawn again as a plan B; the page asked stays.
    evening = {"envies": ["rire"], "diner": False, "day": DAY.isoformat()}
    page = api("/api/soirees", evening)
    later = DAY + timedelta(days=7)
    moved = api(f"/api/parcours/{page['name']}/jour", {"day": later.isoformat()})
    assert not isinstance(moved, tuple), moved
    assert moved["name"] != page["name"] and moved["routes"] and not moved["chosen"]
    kept = 0
    for route in moved["routes"]:
        assert route["day"] == later.isoformat()
        _chains(route)
        before = next((r for r in page["routes"] if r["title"] == route["title"]), None)
        if before:
            hours = {s["id"]: s["start"][11:16] for s in before["steps"]}
            kept += sum(1 for s in route["steps"] if hours.get(s["id"]) == s["start"][11:16])
    assert kept + moved["changed"] >= len(moved["routes"][0]["steps"])
    assert kept > 0  # the same evening, not a new one
    # A day gone, or not a day, is refused.
    assert api(f"/api/parcours/{page['name']}/jour", {"day": "2020-01-01"})[0] == 400
    assert api(f"/api/parcours/{page['name']}/jour", {"day": "demain"})[0] == 400


def test_tonight_an_evening_around_where_the_couple_is_for_the_hours_to_come(api, monkeypatch):
    # « Ce soir » at the Bastille, its hours fixed here (from half an hour on, for three hours) whatever the time of the run.
    start = datetime.combine(DAY, time(19, 30), parcours.PARIS)
    monkeypatch.setattr(quiz, "tonight", lambda now=None: (start, start + timedelta(hours=3)))
    bastille = (48.8532, 2.3692)
    page = api("/api/soirees", {"envies": ["nous"], "diner": False, "maintenant": True, "origin": {"lat": bastille[0], "lon": bastille[1]}})
    assert page["routes"], page
    for route in page["routes"]:
        _chains(route)
        assert route["day"] == DAY.isoformat()
        assert route["steps"][0]["start"] >= start.isoformat() and route["steps"][-1]["end"] <= (start + timedelta(hours=3, minutes=20)).isoformat()
        assert all(parcours.distance_km(bastille, (s["lat"], s["lon"])) <= 2 * parcours.NEAR_KM for s in route["steps"])
