import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from surprise.admin import make_handler
from surprise.collectors import que_faire_a_paris as qfap
from surprise.local_store import LocalStore

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "que_faire_a_paris.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 9, 24, 22, tzinfo=timezone.utc)


@pytest.fixture
def base_url(tmp_path):
    path = tmp_path / "surprise.db"
    results = [qfap.normalize(p, NOW) for p in FIXTURE]
    with LocalStore(path) as store:
        store.save_raw_records([r.raw for r in results])
        store.save_normalized([(r.raw, r.activity, r.rejection) for r in results])
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(path))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def request(url, data=None, content_type="application/json"):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"Content-Type": content_type} if body else {})
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def test_page_is_served(base_url):
    status, body = request(f"{base_url}/admin")
    assert status == 200 and b"<title>Surprise" in body
    assert request(f"{base_url}/")[1] == body  # the root leads to it


def test_status_is_updated_through_the_api(base_url):
    status, _ = request(f"{base_url}/api/activities/que_faire_a_paris/12345/status", {"status": "rejected"})
    assert status == 200
    _, body = request(f"{base_url}/api/activities")
    statuses = {i["external_id"]: i["status"] for i in json.loads(body)}
    assert statuses == {"12345": "rejected", "2": "filtered", "3": "filtered", "4": "proposed"}


@pytest.mark.parametrize(
    ("path", "data", "content_type", "expected"),
    [
        ("que_faire_a_paris/12345/status", {"status": "published"}, "application/json", 400),
        ("que_faire_a_paris/12345/status", {"status": "approved"}, "text/plain", 415),
        ("que_faire_a_paris/inconnu/status", {"status": "approved"}, "application/json", 404),
        ("que_faire_a_paris/12345", {"status": "approved"}, "application/json", 404),
    ],
)
def test_invalid_requests_are_refused(base_url, path, data, content_type, expected):
    status, _ = request(f"{base_url}/api/activities/{path}", data, content_type)
    assert status == expected


def test_source_name_and_ids_with_slash_and_hash(tmp_path):
    from urllib.parse import quote

    from surprise.collectors import paris_zigzag as zz

    path = tmp_path / "surprise.db"
    page = "<p><strong>Bar Test</strong><br />1 rue de Marengo, 75001 Paris</p>"
    [payload] = zz.parse_article("https://www.pariszigzag.fr/bar-restaurant/bar/test/", page)
    result = zz.normalize(payload, NOW)
    with LocalStore(path) as store:
        store.save_raw_records([result.raw])
        store.save_normalized([(result.raw, result.activity, result.rejection)])
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(path))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        [item] = json.loads(request(f"{base_url}/api/activities")[1])
        assert item["source_name"] == "Paris ZigZag"
        assert item["external_id"] == "bar-restaurant/bar/test#bar-test"
        status, _ = request(
            f"{base_url}/api/activities/paris_zigzag/{quote(item['external_id'], safe='')}/status", {"status": "approved"}
        )
        assert status == 200
        assert json.loads(request(f"{base_url}/api/activities")[1])[0]["status"] == "approved"
    finally:
        server.shutdown()
        server.server_close()


def test_meta_lists_categories_and_sources(base_url):
    meta = json.loads(request(f"{base_url}/api/meta")[1])
    assert meta["categories"]["humour"] == "Humour / stand-up"
    assert meta["sources"]["paris_zigzag"] == "Paris ZigZag"


def test_place_photo_needs_a_key_and_a_valid_id(base_url, monkeypatch):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    assert request(f"{base_url}/api/place-photo?place_id=ChIJabcdefghij")[0] == 503
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")
    assert request(f"{base_url}/api/place-photo?place_id=../../etc")[0] == 400
