"""Evenings composed through the API from the activities of the project's base (tests/prod_activities.py: read in
production, never written), for the next Friday as the app proposes it: for each wish, several routes that chain, each
step with its own text; a band's evenings; and a couple's journey, a step changed, a route drawn again, one kept and the
next evening without it. Everything the API writes stays in the test's own store; no booking engine is asked."""

import pytest

import prod_activities
from surprise import images, parcours
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
