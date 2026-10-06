"""The couple's whole journey through the API, as the app makes it: profile, an evening composed, its steps changed
and taken out, a route drawn again, one kept, and the next evening without its activities."""

import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from surprise import parcours, quiz
from test_parcours import DAY, at, item
from test_quiz import ANSWERS


def _shown(external_id, title, categories, **extra):
    entry = item(external_id, title, categories, **extra)
    entry["enrichment"]["description"] = f"{title}, à deux."
    return entry


# An evening around the Marais (a Friday's, unless another day is given; the browser tests take the next Friday):
# shows to laugh at, games, bars to wait in between.
def catalogue(day=DAY):
    return [
        _shown("standup", "Stand-up au sous-sol", ["humour"], occurrences=[at(19, 30, day)], venue="Cave à rire"),
        _shown("impro", "Match d'improvisation", ["humour"], occurrences=[at(20, 0, day)], lat=48.861, venue="Théâtre impro"),
        _shown("comedy", "Comedy club en anglais", ["humour"], occurrences=[at(21, 30, day)], lat=48.862, venue="Comedy club"),
        _shown("plateau", "Plateau d'humoristes", ["humour"], occurrences=[at(22, 0, day)], lon=2.351, venue="Plateau"),
        _shown("cafe", "Café-théâtre", ["humour"], occurrences=[at(21, 0, day)], lat=48.859, venue="Café-théâtre"),
        _shown("drag", "Cabaret drag", ["humour"], occurrences=[at(22, 30, day)], lat=48.8605, venue="Cabaret"),
        _shown("seul", "Seul en scène", ["humour"], occurrences=[at(21, 45, day)], lat=48.8615, venue="Petite salle"),
        _shown("openmic", "Open mic", ["humour"], occurrences=[at(22, 15, day)], lat=48.8602, venue="Sous-sol"),
        _shown("minuit", "Impro de minuit", ["humour"], occurrences=[at(22, 45, day)], lon=2.3495, venue="Salle de minuit"),
        _shown("blindtest", "Blind test", ["jeux"], occurrences=[at(21, 0, day)], lat=48.8603, venue="Bar à jeux"),
        _shown("piste", "Jeu de piste", ["jeux"], occurrences=[at(19, 0, day)], lat=48.8598, lon=2.3512, venue="Place des Vosges"),
        _shown("pirates", "Escape game des pirates", ["jeux"], occurrences=[at(19, 30, day)], lat=48.8607, lon=2.3488, venue="Manoir"),
        _shown("bowling", "Bowling rétro", ["jeux"], occurrences=[at(20, 45, day)], lat=48.8611, lon=2.3509, venue="Bowling"),
        _shown("billard", "Tournoi de billard", ["jeux"], occurrences=[at(21, 15, day)], lat=48.8604, lon=2.3493, venue="Billard"),
        _shown("minigolf", "Mini-golf fluo", ["jeux"], occurrences=[at(20, 30, day), at(21, 30, day)], lat=48.8609, lon=2.3502, venue="Golf fluo"),
        _shown("escape", "Escape game du Louvre", ["jeux"], occurrences=[at(19, 0, day), at(20, 30, day)], lon=2.349, venue="Escape"),
        _shown("tresor", "Chasse au trésor du Marais", ["jeux"], occurrences=[at(19, 15, day)], lat=48.8595, venue="Rue des Archives"),
        _shown("quiz", "Quiz au pub", ["jeux"], occurrences=[at(20, 30, day)], lat=48.8608, lon=2.352, venue="Pub"),
        _shown("bar", "Bar à cocktails", ["bar"], kind="permanent", hours="Mo-Su 18:00-02:00", lat=48.8612, venue="Bar"),
        _shown("cave", "Bar à vins", ["bar"], kind="permanent", hours="Mo-Su 17:00-01:00", lon=2.3505, venue="Cave"),
    ]


CATALOGUE = catalogue()
JSON_HEADERS = {"Content-Type": "application/json"}


@pytest.fixture
def base():
    """The activities the server composes from (test_real_catalogue: real ones)."""
    return parcours.Base(CATALOGUE, {(i["source_id"], i["external_id"]): 35 for i in CATALOGUE})


@pytest.fixture
def api(tmp_path, monkeypatch, base):
    """The server, on a store of its own, with `base` for its activities and no live check nor Claude."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(parcours, "DB", tmp_path / "s.db")  # make_handler sets it: put back after
    monkeypatch.setattr(parcours.Base, "load", classmethod(lambda cls, store: base))
    server = ThreadingHTTPServer(("127.0.0.1", 0), quiz.make_handler(tmp_path / "s.db", checks=0))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"

    def call(path, body=None):
        """The answer's JSON, or (code, error) when refused."""
        request = Request(url + path, data=None if body is None else json.dumps(body).encode(), headers=JSON_HEADERS)
        try:
            return json.load(urlopen(request))
        except HTTPError as error:
            return error.code, json.load(error)["error"]

    call.url = url
    yield call
    server.shutdown()


def _keys(page):
    return [[step["id"] for step in route["steps"]] for route in page["routes"]]


def _chains(route):
    for previous, step in zip(route["steps"], route["steps"][1:]):
        assert previous["end"] <= step["start"], (previous["title"], step["title"])


def test_a_couple_composes_changes_and_keeps_an_evening(api):
    profile = api("/api/profiles", {"answers": ANSWERS})["profile"]
    evening = {"envies": ["rire"], "diner": False, "day": DAY.isoformat(), "profile": profile}
    page = api("/api/soirees", evening)
    name = page["name"]
    assert page["days"] == [DAY.isoformat()] and not page["chosen"] and not page["naming"]
    assert page["routes"] and api(f"/api/parcours/{name}") == page
    shown = {key for route in _keys(page) for key in route}
    for route in page["routes"]:
        _chains(route)
        assert route["title"] and route["secret_title"] and all(step["title"] and step["image_url"] and step["text"] for step in route["steps"])
    # No activity in two routes of the evening.
    assert sum(map(len, _keys(page))) == len(shown)

    # One step changed (the last that can be), again and again: never an activity the page had, until none is left.
    for position in reversed(range(len(page["routes"][0]["steps"]))):
        changes = 0
        while not isinstance(changed := api(f"/api/parcours/{name}/routes/0/steps/{position}", {}), tuple):
            new = changed["routes"][0]["steps"][position]["id"]
            assert new not in shown
            shown.add(new)
            _chains(changed["routes"][0])
            page, changes = changed, changes + 1
        assert changed == (409, "plus d'autre activité qui s'enchaîne à cette étape ce soir-là")
        if changes:
            break
    assert changes
    assert api(f"/api/parcours/{name}") == page

    # The steps of the last route taken out one by one; the last one stays.
    last = len(page["routes"]) - 1
    while (steps := len(page["routes"][last]["steps"])) > 1:
        page = api(f"/api/parcours/{name}/routes/{last}/steps/0/remove", {})
        assert len(page["routes"][last]["steps"]) == steps - 1
    assert api(f"/api/parcours/{name}/routes/{last}/steps/0/remove", {}) == (409, "une soirée garde au moins une étape")

    # The route kept: the page's only one, for good.
    kept = page["routes"][0]
    page = api(f"/api/parcours/{name}/routes/0/choose", {})
    assert page["chosen"] and [route["index"] for route in page["routes"]] == [0]
    assert [step["id"] for step in page["routes"][0]["steps"]] == [step["id"] for step in kept["steps"]]
    assert api(f"/api/parcours/{name}") == page

    # The next evening, its history given, never proposes what was kept.
    following = api("/api/soirees", {**evening, "done": [name]})
    assert following["name"] != name
    kept_ids = {step["id"] for step in kept["steps"]}
    assert not kept_ids & {key for route in _keys(following) for key in route}


def test_a_route_is_drawn_again_without_its_activities(api):
    # Laughing and playing: enough outings left, in either catalogue, for a whole route none of the three proposed
    # used (to laugh alone, the real quarter's shows run out: a 409, rightly).
    page = api("/api/soirees", {"envies": ["rire", "jouer"], "diner": False, "day": DAY.isoformat()})
    name, before = page["name"], set(_keys(page)[0])
    redrawn = api(f"/api/parcours/{name}/routes/0", {})
    assert set(_keys(redrawn)[0]) != before and len(redrawn["routes"]) == len(page["routes"])
    _chains(redrawn["routes"][0])
    assert api(f"/api/parcours/{name}") == redrawn


# The stand-ups of the catalogue: one kind of outing (surprise.parcours.kinds).
STAND_UPS = {f"test:{i['external_id']}" for i in CATALOGUE if "stand_up" in parcours.kinds(i)}


def test_the_couples_votes_shape_their_next_evenings(api):
    evening = {"envies": ["rire", "jouer"], "diner": False, "day": DAY.isoformat()}
    page = api("/api/soirees", evening)
    proposed = {key for route in _keys(page) for key in route}
    assert proposed & STAND_UPS
    # One activity voted down: never proposed again.
    down = sorted(proposed)[0]
    following = api("/api/soirees", {**evening, "votes": {down: -1}})
    assert following["routes"] and down not in {key for route in _keys(following) for key in route}
    # Two stand-ups voted down: no stand-up any more, the games stay. The tastes are kept with the evening, for the
    # steps drawn again once it is kept (plan B).
    votes = {"test:standup": -1, "test:comedy": -1, "test:pirates": 1}
    page = api("/api/soirees", {**evening, "votes": votes})
    assert page["routes"] and not {key for route in _keys(page) for key in route} & STAND_UPS
    assert parcours.load(page["name"])["requests"][0].tastes == {"stand_up": -2, "comedie": -1, "escape_game": 1}
    # Votes the page could not have sent are dropped, the evening composed all the same.
    assert api("/api/soirees", {**evening, "votes": ["test:standup"]})["routes"]
    assert api("/api/soirees", {**evening, "votes": {"test:standup": 5, "standup": -1}})["routes"]


def test_the_api_refuses_what_it_cannot_do(api):
    assert api("/api/parcours/absente") == (404, "introuvable")
    assert api("/api/parcours/absente/routes/0/steps/1", {}) == (409, "parcours introuvable : relancez la composition")
    assert api("/api/parcours/absente/routes/0/choose", {}) == (409, "parcours introuvable : relancez la composition")
    assert api("/api/inconnue", {}) == (404, "introuvable")
    for body, error in [
        ({"envies": ["inconnue"], "diner": True}, "au moins une envie"),
        ({"envies": ["rire"], "diner": "oui"}, "dîner ou pas ?"),
        ({"envies": ["rire"], "diner": True, "budget": 0}, "budget invalide"),
        ({"envies": ["rire"], "diner": True, "budget": True}, "budget invalide"),
        ({"envies": ["rire"], "diner": True, "profile": {"vibes": []}}, "profil invalide"),
    ]:
        assert api("/api/soirees", body) == (400, error)
