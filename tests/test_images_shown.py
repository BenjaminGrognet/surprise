"""A step's image on the couple's pages: a kept evening's copied here, and one a page could not show reported, then
replaced by the official site's or recorded dead (parcours.broken_image, POST /api/images/broken)."""

from urllib.request import urlopen

import httpx
import pytest
import respx

from surprise import images, parcours
from surprise.local_store import open_store
from surprise.parcours import keep_images  # the real one: conftest leaves it out
from test_journey import DAY, api, catalogue  # noqa: F401 (the fixture)

JPEG = {"Content-Type": "image/jpeg"}
PHOTO = "https://example.org/standup.jpg"  # the stand-up's, in CATALOGUE
NEW = "https://www.cave-a-rire.example/affiche.jpg"


@pytest.fixture
def base():
    """test_journey's activities, a copy of their own: a report changes an image."""
    items = catalogue()
    return parcours.Base(items, {(i["source_id"], i["external_id"]): 35 for i in items})


@pytest.fixture(autouse=True)
def checked_afresh(monkeypatch):
    monkeypatch.setattr(parcours, "_IMAGES", {})
    monkeypatch.setattr(parcours, "_REPORTED", {})


@pytest.fixture
def sites():
    with respx.mock(assert_all_called=False) as mock:
        yield mock


def _compose(api):
    return api("/api/soirees", {"envies": ["rire"], "diner": False, "day": DAY.isoformat()})


def test_a_kept_evening_is_shown_with_its_images_copied_here(api, sites, monkeypatch):
    monkeypatch.setattr(parcours, "keep_images", keep_images)
    sites.get(url__regex=r"https://example\.org/\w+\.jpg").respond(200, content=b"jpeg", headers=JPEG)
    page = _compose(api)
    assert all(s["image_url"].startswith("https://example.org/") for r in page["routes"] for s in r["steps"])
    kept = api(f"/api/parcours/{page['name']}/routes/0/choose", {})
    steps = kept["routes"][0]["steps"]
    assert all(s["image_url"].startswith("/images/") for s in steps)
    assert api(f"/api/parcours/{page['name']}") == kept
    with urlopen(api.url + steps[0]["image_url"]) as response:
        assert response.headers["Content-Type"] == "image/jpeg" and response.read() == b"jpeg"


def test_an_image_that_cannot_be_had_stays_the_sites(api, sites, monkeypatch):
    monkeypatch.setattr(parcours, "keep_images", keep_images)
    sites.get(url__regex=r"https://example\.org/.*").respond(404)
    page = _compose(api)
    kept = api(f"/api/parcours/{page['name']}/routes/0/choose", {})
    assert [s["image_url"] for s in kept["routes"][0]["steps"]] == [s["image_url"] for s in page["routes"][0]["steps"]]


def _dead(url):
    with open_store(parcours.DB) as store:
        return store.page_checks().get(url, (None, None, None))[1]


def test_a_dead_image_reported_is_replaced_by_the_official_sites(api, base, sites, monkeypatch):
    sites.get(PHOTO).respond(404)
    monkeypatch.setattr(images, "replacement", lambda client, item, dead: NEW)
    assert api("/api/images/broken", {"id": "test:standup", "url": PHOTO}) == {"image_url": NEW}
    assert _dead(PHOTO) and images.of(base.by_key[("test", "standup")]) == NEW
    # The pages drawn before still name the old one: their next report gets the new one, without asking again.
    assert api("/api/images/broken", {"id": "test:standup", "url": PHOTO}) == {"image_url": NEW}
    assert len(sites.calls) == 1


def test_a_dead_image_without_another_is_recorded_dead(api, sites, monkeypatch):
    sites.get("https://example.org/impro.jpg").respond(404)
    monkeypatch.setattr(images, "replacement", lambda client, item, dead: None)
    assert api("/api/images/broken", {"id": "test:impro", "url": "https://example.org/impro.jpg"}) == {"image_url": None}
    assert _dead("https://example.org/impro.jpg") and parcours._IMAGES["https://example.org/impro.jpg"] is False


@pytest.mark.parametrize("answer", [httpx.Response(200, content=b"jpeg", headers=JPEG), httpx.Response(429), httpx.ConnectTimeout("lent")])
def test_an_image_that_loads_here_or_does_not_answer_is_left_as_it_is(api, sites, answer):
    sites.get("https://example.org/comedy.jpg").mock(side_effect=[answer])
    assert api("/api/images/broken", {"id": "test:comedy", "url": "https://example.org/comedy.jpg"}) == {"image_url": None}
    assert _dead("https://example.org/comedy.jpg") is None


def test_a_report_names_a_known_activity_and_asks_no_site_for_another_image(api, sites):
    assert api("/api/images/broken", {"id": "test:absente", "url": PHOTO}) == {"image_url": None}
    # An image the activity has not (any more): the one it has, unchecked.
    assert api("/api/images/broken", {"id": "test:standup", "url": "https://ailleurs.example/x.jpg"}) == {"image_url": PHOTO}
    assert api("/api/images/broken", {"id": "standup", "url": PHOTO}) == (400, "étape ou image manquante")
    assert api("/api/images/broken", {"id": "test:standup"}) == (400, "étape ou image manquante")
    assert not sites.calls
