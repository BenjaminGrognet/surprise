import json
import threading
from datetime import date
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from surprise import parcours, quiz
from surprise.categories import CATEGORIES
from surprise.local_store import open_store
from surprise.tags import TAGS, VIBES

ANSWERS = {
    "couple": "longue",
    "debut_soiree": "cocon",
    "energie": 2,
    "reussie": ["yeux", "musique"],
    "audace": "surprenez",
    "musique": ["jazz"],
    "eviter": ["noir", "peur", "maillot"],
    "budget": "genereux",
    "premiere": "2026-10-09",
    "prenoms": "Léa & Sam",
}


def test_questions_only_name_known_vibes():
    for question in quiz.QUESTIONS:
        for option in question.get("options") or []:
            assert set(option.get("vibes") or {}) <= VIBES.keys(), option
    for wish in quiz.ENVIES + quiz.OCCASIONS:
        assert set(wish["vibes"]) <= VIBES.keys(), wish


def test_refusals_name_known_tags_or_categories():
    known = TAGS.keys() | CATEGORIES.keys() | {"interactif", "cocktails", "vins nature"}
    refusals = [o for q in quiz.QUESTIONS if q["id"] == "eviter" for o in q["options"]] + quiz.ENVIES
    for option in refusals:
        assert set(option.get("avoid") or []) <= known, option


def test_no_precise_hour_is_asked():
    assert not [q for q in quiz.QUESTIONS if q["kind"] not in {"single", "multi", "scale", "date", "text"}]
    assert "start" not in quiz.profile_from(ANSWERS)


def test_profile_from_answers():
    profile = quiz.profile_from(ANSWERS)
    assert profile["vibes"][0] == "romantique" and len(profile["vibes"]) <= 4
    assert profile["persona"]["name"] == "Les Romantiques"
    assert profile["audace"] == 0.7 and profile["budget"] == 200
    assert {"dans_le_noir", "frisson", "spa", "baignade"} <= set(profile["avoid"]) and profile["genres"] == ["jazz"]
    assert (profile["first_day"], profile["names"]) == ("2026-10-09", "Léa & Sam")
    assert "end" not in profile and "dinner" not in profile


def test_music_genres_reach_the_evening():
    profile = quiz.profile_from({**ANSWERS, "musique": ["jazz", "rock", "classique"]})
    assert profile["genres"] == ["classique", "jazz", "rock"] and "chandelles" in profile["prefer"]
    assert quiz.valid_profile({**profile, "genres": ["jazz", "bogus"]})["genres"] == ["jazz"]
    [request] = quiz.requests_for(profile)
    assert request.genres == {"classique", "jazz", "rock"}


def test_empty_answers_still_make_a_profile():
    profile = quiz.profile_from({"premiere": "2026-02-31"})
    assert profile["vibes"] == ["romantique"] and profile["first_day"] is None


def test_requests_follow_the_profile():
    [request] = quiz.requests_for(quiz.profile_from(ANSWERS))
    assert request.day == date(2026, 10, 9) and request.start.hour == 19 and request.start.minute == 0
    assert request.end.day == 10 and request.audace == 0.7 and "dans_le_noir" in request.avoid
    assert set(request.vibes) == set(quiz.profile_from(ANSWERS)["vibes"])


def test_each_evening_has_its_own_wish():
    profile = quiz.profile_from(ANSWERS)
    [party] = quiz.requests_for(profile, [date(2026, 10, 10)], ["fete"])
    assert party.vibes[:2] == ["fete", "musique"] and party.end.hour == 3 and party.start.hour == 20
    assert "spa" in party.avoid and party.budget == 200  # the profile's refusals and budget stay
    [cosy] = quiz.requests_for(profile, [date(2026, 10, 11)], ["cocooning"], occasion="anniversaire")
    assert "detente" in cosy.vibes and cosy.end.hour == 23 and {"nuit", "electro", "baignade"} <= cosy.avoid
    [bold] = quiz.requests_for(profile, envies=["surprise"])
    assert bold.audace == 1.0 and "insolite" in bold.vibes


def test_up_to_three_wishes_mix_in_one_evening():
    profile = quiz.profile_from(ANSWERS)
    night = quiz.evening(profile, ["cocooning", "fete", "rire", "jouer"])
    assert night["envies"] == ["cocooning", "fete", "rire"]  # the fourth is dropped
    assert night["vibes"][:3] == ["detente", "fete", "rire"] and len(night["vibes"]) <= quiz.MAX_VIBES
    # The party keeps its clubs and its late end; cocooning still leaves out what nobody asked for.
    assert not {"nuit", "electro", "danse"} & set(night["avoid"]) and {"sport", "grande_salle", "spa"} <= set(night["avoid"])
    assert (night["start"], night["end"]) == ("20:00", "03:30")
    assert quiz.evening(profile, ["air", "cocooning"])["start"] == "18:30"
    assert quiz.evening(profile)["vibes"] == profile["vibes"]


def test_start_end_and_budget_are_chosen_per_evening_not_in_the_profile():
    assert not any(q["id"] in {"fin"} for q in quiz.QUESTIONS)
    profile = quiz.profile_from(ANSWERS)  # budget "genereux" -> 200, no start/end in the profile
    [normal] = quiz.requests_for(profile, [date(2026, 10, 10)], ["nous"])
    assert normal.start.hour == 19 and normal.end.hour == 0 and normal.budget == 200  # the profile's defaults
    [early] = quiz.requests_for(profile, [date(2026, 10, 10)], ["nous"], start="tot")
    assert early.start.hour == 17
    [late] = quiz.requests_for(profile, [date(2026, 10, 10)], ["nous"], end="danser")
    assert late.end.hour == 3
    [cheaper] = quiz.requests_for(profile, [date(2026, 10, 10)], ["nous"], budget=60)
    assert cheaper.budget == 60


def test_valid_profile_reshapes_the_trusted_fields():
    profile = quiz.profile_from(ANSWERS)
    reshaped = quiz.valid_profile(profile)
    assert reshaped["vibes"] == profile["vibes"] and reshaped["budget"] == profile["budget"]
    assert reshaped["audace"] == profile["audace"] and reshaped["first_day"] == profile["first_day"]


def test_valid_profile_rejects_the_wrong_shape():
    assert quiz.valid_profile("pas un profil") is None
    assert quiz.valid_profile({"vibes": ["romantique"]}) is None  # no audace, no budget
    clamped = quiz.valid_profile({"vibes": ["pas-une-vibe", "romantique"], "audace": 5, "avoid": [1], "budget": 99999})
    assert clamped["vibes"] == ["romantique"] and clamped["audace"] == 1.0 and clamped["avoid"] == [] and clamped["budget"] == 1000.0


def test_valid_votes_keeps_an_activity_and_a_plus_or_minus_one():
    votes = {"fever:12": 1, "osm_loisirs:node:5": -1, "sans-source": 1, ":15": -1, "fever:13": 2, "fever:14": True, "fever:16": "1"}
    assert quiz.valid_votes(votes) == {("fever", "12"): 1, ("osm_loisirs", "node:5"): -1}
    assert quiz.valid_votes(["fever:12"]) == {} and quiz.valid_votes(None) == {}
    assert len(quiz.valid_votes({f"fever:{n}": 1 for n in range(2 * quiz.MAX_VOTES)})) == quiz.MAX_VOTES


def test_profile_is_computed_through_the_api(tmp_path, monkeypatch):
    # The site is the app's web build: a stand-in for app/dist.
    web = tmp_path / "dist"
    (web / "_expo").mkdir(parents=True)
    (web / "index.html").write_text("accueil de l'app", encoding="utf-8")
    (web / "soiree.html").write_text("soirée de l'app", encoding="utf-8")
    (web / "_expo" / "entry.js").write_text("app()", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("hors du site", encoding="utf-8")
    monkeypatch.setattr(quiz, "WEB", web)
    server = ThreadingHTTPServer(("127.0.0.1", 0), quiz.make_handler(tmp_path / "s.db", checks=0))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        body = json.dumps({"answers": ANSWERS}).encode()
        created = json.load(urlopen(Request(f"{url}/api/profiles", data=body, headers={"Content-Type": "application/json"})))
        assert created["profile"]["persona"]["name"] == "Les Romantiques"
        with open_store(tmp_path / "s.db") as store:
            assert json.loads(store._run("select profile from profiles").fetchone()[0]) == created["profile"]
        evening = json.load(urlopen(f"{url}/api/soiree"))
        assert evening["max"] == 3 and evening["envies"] and evening["occasions"]
        assert evening["starts"] and evening["ends"] and evening["budgets"]
        # One site: the app's pages and scripts, and the moderation page with its API.
        assert urlopen(f"{url}/").read() == "accueil de l'app".encode() and urlopen(f"{url}/soiree").read() == "soirée de l'app".encode()
        script = urlopen(f"{url}/_expo/entry.js")
        assert script.headers["Content-Type"] == "text/javascript; charset=utf-8"
        with pytest.raises(HTTPError):
            urlopen(f"{url}/..%2Fsecret.txt")
        assert b"<title>Surprise" in urlopen(f"{url}/admin").read() and json.load(urlopen(f"{url}/api/meta"))["vibes"]
        for body, code in [({"envies": [], "diner": True}, 400), ({"envies": ["fete"]}, 400), ({"envies": ["fete"], "diner": False, "profile": "inconnu"}, 400)]:
            request = Request(f"{url}/api/soirees", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            try:
                urlopen(request)
            except HTTPError as error:
                assert error.code == code
            else:
                raise AssertionError(body)
    finally:
        server.shutdown()


def test_the_route_kept_is_the_pages_only_one(tmp_path, monkeypatch):
    from test_parcours import _night

    monkeypatch.setattr(parcours, "DB", tmp_path / "s.db")  # make_handler sets it: put back after
    server =ThreadingHTTPServer(("127.0.0.1", 0), quiz.make_handler(tmp_path / "s.db", checks=0))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        req, _, route = _night()
        route.request = req
        parcours.save("essai", {"routes": [route, route], "requests": [req], "seen": set()})
        url = f"http://127.0.0.1:{server.server_port}/api/parcours"
        assert len(json.load(urlopen(f"{url}/essai"))["routes"]) == 2

        def choose(name, index):
            post = Request(f"{url}/{name}/routes/{index}/choose", data=b"{}", headers={"Content-Type": "application/json"})
            return json.load(urlopen(post))

        page = choose("essai", 1)
        assert page["chosen"] and [r["index"] for r in page["routes"]] == [0]
        assert json.load(urlopen(f"{url}/essai")) == page
        with pytest.raises(HTTPError) as error:
            choose("essai", 1)
        assert error.value.code == 409
    finally:
        server.shutdown()


def test_each_evening_says_whether_they_eat():
    profile = quiz.profile_from(ANSWERS)
    [ate] = quiz.requests_for(profile, [date(2026, 10, 10)], ["romantique"], dinner=False)
    assert ate.no_dinner and not ate.dinner  # an explicit "no" wins over the wish
    [eats] = quiz.requests_for(quiz.profile_from({}), [date(2026, 10, 10)], ["fete"], dinner=True)
    assert eats.dinner and not eats.no_dinner  # an explicit "yes" even without a wish that calls for one
    [unsaid] = quiz.requests_for(profile, [date(2026, 10, 10)], ["romantique"])
    assert unsaid.dinner and not unsaid.no_dinner  # not said: inferred from the wish ("romantique" wants one)
    [unwished] = quiz.requests_for(profile, [date(2026, 10, 10)], ["fete"])
    assert not unwished.dinner and not unwished.no_dinner  # "fete" doesn't call for one
    assert not unwished.overnight
    [out] = quiz.requests_for(profile, [date(2026, 10, 10)], ["romantique"], overnight=True)
    assert out.overnight


def test_a_bands_wishes_and_occasions_name_known_vibes_and_tags():
    for wish in quiz.SQUAD_ENVIES + quiz.SQUAD_OCCASIONS:
        assert set(wish["vibes"]) <= VIBES.keys(), wish
        assert set(wish.get("prefer") or []) <= TAGS.keys(), wish
    # The mood cards are wishes, the band's never a couple's.
    assert set(quiz.MOODS) <= quiz.ENVIE_KEYS.keys() and set(quiz.SQUAD_MOODS) <= quiz.SQUAD_ENVIE_KEYS.keys()
    assert not {"romantique", "pimenter", "cocooning", "nous"} & quiz.SQUAD_ENVIE_KEYS.keys()


def test_a_bands_evening_is_its_own():
    band = quiz.squad_profile()
    [hen] = quiz.requests_for(band, [date(2026, 10, 10)], ["bande", "chanter"], "evjf", budget=240, party=4, formule="squad")
    assert (hen.party, hen.formule, hen.budget) == (4, "squad", 240) and hen.squad
    # "Fidèles à la bande": the band's vibes, not a couple's romance; a hen party's offers and karaoke come first.
    assert "romantique" not in hen.vibes and {"rire", "fete"} <= set(hen.vibes)
    assert {"evjf", "karaoke", "quiz"} <= hen.prefer
    # The same word, another occasion: a band's birthday is a party, a couple's a romantic dinner.
    [birthday] = quiz.requests_for(band, [date(2026, 10, 10)], ["fete"], "anniversaire", party=8, formule="squad")
    [theirs] = quiz.requests_for(band, [date(2026, 10, 10)], ["fete"], "anniversaire")
    assert "romantique" not in birthday.vibes and "romantique" in theirs.vibes and not theirs.squad


def test_a_band_says_its_vibes_its_own_way():
    assert set(quiz.SQUAD_VIBE_LABELS) <= VIBES.keys()
    assert quiz.SQUAD_VIBE_LABELS["rire"] != VIBES["rire"]["label"] and "Paillettes" == quiz.SQUAD_VIBE_LABELS["romantique"]
