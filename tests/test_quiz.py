import json
import threading
from datetime import date
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from surprise import quiz
from surprise.categories import CATEGORIES
from surprise.local_store import LocalStore
from surprise.tags import TAGS, VIBES

ANSWERS = {
    "couple": "longue",
    "debut_soiree": "cocon",
    "energie": 2,
    "reussie": ["yeux", "musique"],
    "audace": "surprenez",
    "assiette": "table",
    "musique": ["jazz"],
    "fin": "verre",
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
    assert {"romantique", "savourer"} == set(profile["vibes"][:2]) and len(profile["vibes"]) <= 4
    assert profile["persona"]["name"] == "Les Romantiques"
    assert profile["audace"] == 0.7 and profile["dinner"] and profile["budget"] == 200
    assert {"dans_le_noir", "frisson", "spa", "baignade"} <= set(profile["avoid"]) and profile["prefer"] == ["jazz"]
    assert (profile["first_day"], profile["end"], profile["names"]) == ("2026-10-09", "00:30", "Léa & Sam")


def test_empty_answers_still_make_a_profile():
    profile = quiz.profile_from({"premiere": "2026-02-31"})
    assert profile["vibes"] == ["romantique"] and profile["first_day"] is None


def test_requests_follow_the_profile():
    [request] = quiz.requests_for(quiz.profile_from(ANSWERS))
    assert request.day == date(2026, 10, 9) and request.start.hour == 19 and request.start.minute == 0
    assert request.end.day == 10 and request.dinner and request.audace == 0.7 and "dans_le_noir" in request.avoid
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


def test_profile_is_stored_through_the_api(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), quiz.make_handler(tmp_path / "s.db", checks=0))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        body = json.dumps({"answers": ANSWERS}).encode()
        created = json.load(urlopen(Request(f"{url}/api/profiles", data=body, headers={"Content-Type": "application/json"})))
        assert created["profile"]["persona"]["name"] == "Les Romantiques"
        fetched = json.load(urlopen(f"{url}/api/profiles/{created['id']}"))
        assert fetched["answers"]["prenoms"] == "Léa & Sam"
        with LocalStore(tmp_path / "s.db") as store:
            assert [p["id"] for p in store.list_profiles()] == [created["id"]]
        evening = json.load(urlopen(f"{url}/api/soiree"))
        assert evening["max"] == 3 and evening["envies"] and evening["occasions"]
        assert b"Ce soir" in urlopen(f"{url}/soiree").read() and urlopen(f"{url}/client.js").status == 200
        for body, code in [({"envies": [], "diner": True}, 400), ({"envies": ["fete"]}, 400), ({"envies": ["fete"], "diner": False, "profile": "inconnu"}, 404)]:
            request = Request(f"{url}/api/soirees", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            try:
                urlopen(request)
            except HTTPError as error:
                assert error.code == code
            else:
                raise AssertionError(body)
    finally:
        server.shutdown()


def test_each_evening_says_whether_they_eat():
    profile = quiz.profile_from(ANSWERS)  # a profile that likes a fine table
    assert profile["dinner"]
    [ate] = quiz.requests_for(profile, [date(2026, 10, 10)], ["romantique"], dinner=False)
    assert ate.no_dinner and not ate.dinner
    [eats] = quiz.requests_for(quiz.profile_from({}), [date(2026, 10, 10)], ["fete"], dinner=True)
    assert eats.dinner and not eats.no_dinner
    [unsaid] = quiz.requests_for(profile, [date(2026, 10, 10)], ["fete"])
    assert unsaid.dinner and not unsaid.no_dinner
