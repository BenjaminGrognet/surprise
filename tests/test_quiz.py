import json
import threading
from datetime import date
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

from surprise import quiz
from surprise.local_store import LocalStore
from surprise.tags import VIBES

ANSWERS = {
    "occasion": "anniversaire",
    "debut_soiree": "cocon",
    "energie": 2,
    "reussie": ["yeux", "musique"],
    "audace": "surprenez",
    "assiette": "table",
    "musique": ["jazz"],
    "fin": "verre",
    "eviter": ["noir", "peur"],
    "budget": "genereux",
    "quand": {"day": "2026-10-09", "start": "19:30"},
    "prenoms": "Léa & Sam",
}


def test_questions_only_name_known_vibes():
    for question in quiz.QUESTIONS:
        for option in question.get("options") or []:
            assert set(option.get("vibes") or {}) <= VIBES.keys(), option


def test_profile_from_answers():
    profile = quiz.profile_from(ANSWERS)
    assert {"romantique", "savourer"} == set(profile["vibes"][:2]) and len(profile["vibes"]) <= 4
    assert profile["persona"]["name"] == "Les Romantiques"
    assert profile["audace"] == 0.7 and profile["dinner"] and profile["budget"] == 200
    assert {"dans_le_noir", "frisson"} <= set(profile["avoid"]) and profile["prefer"] == ["jazz"]
    assert (profile["day"], profile["start"], profile["end"], profile["names"]) == ("2026-10-09", "19:30", "00:30", "Léa & Sam")


def test_empty_answers_still_make_a_profile():
    profile = quiz.profile_from({})
    assert profile["vibes"] == ["romantique"] and profile["start"] == "19:00"


def test_requests_follow_the_profile():
    [request] = quiz.requests_for(quiz.profile_from(ANSWERS))
    assert request.day == date(2026, 10, 9) and request.start.hour == 19 and request.start.minute == 30
    assert request.end.day == 10 and request.dinner and request.audace == 0.7 and "dans_le_noir" in request.avoid


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
    finally:
        server.shutdown()
