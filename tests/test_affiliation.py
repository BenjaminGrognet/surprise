"""Partner links (surprise.affiliation): with the partner's id, a booking site's link becomes its affiliate link, the
evening's page as its sub-id; without it, or for a site without a programme, the link stays; never twice its id. The
evenings served carry them, and say which they are."""

from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from surprise import affiliation, parcours
from test_parcours import _night

GYG = "https://www.getyourguide.fr/paris-l16/croisiere-t1234/?ranking_uuid=x"


@pytest.fixture(autouse=True)
def no_partner(monkeypatch):
    for key in ("GETYOURGUIDE_PARTNER_ID", "CIVITATIS_AID", "AWIN_PUBLISHER_ID", "AWIN_MERCHANTS"):
        monkeypatch.delenv(key, raising=False)


def query(url):
    return {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}


def test_without_a_partner_id_every_link_stays():
    assert affiliation.partner(GYG, "soiree-ab") == (GYG, False)
    assert affiliation.partner(None, "soiree-ab") == (None, False)


def test_getyourguide_and_civitatis_take_their_id_and_the_evening_once(monkeypatch):
    monkeypatch.setenv("GETYOURGUIDE_PARTNER_ID", "SD42")
    monkeypatch.setenv("CIVITATIS_AID", "777")
    link, partnered = affiliation.partner(GYG, "soiree-ab")
    assert partnered and link.startswith("https://www.getyourguide.fr/paris-l16/croisiere-t1234/?")
    assert query(link) == {"ranking_uuid": "x", "partner_id": "SD42", "cmp": "soiree-ab"}
    # Already a partner link (the same evening served again): its id once, never twice.
    again, _ = affiliation.partner(link, "soiree-ab")
    assert again == link and again.count("partner_id=") == 1
    other = "https://www.getyourguide.com/x?partner_id=AUTRE"
    assert query(affiliation.partner(other, "soiree-cd")[0])["partner_id"] == "SD42"
    link, partnered = affiliation.partner("https://www.civitatis.com/fr/paris/visite-montmartre/", "soiree-ab")
    assert partnered and query(link) == {"aid": "777", "cmp": "soiree-ab"}


def test_awin_wraps_the_sites_it_serves(monkeypatch):
    monkeypatch.setenv("AWIN_PUBLISHER_ID", "987654")
    monkeypatch.setenv("AWIN_MERCHANTS", "fnacspectacles.com:1234, thefork.fr:5678")
    original = "https://www.fnacspectacles.com/event/le-cabaret-1.htm?x=1&y=2"
    link, partnered = affiliation.partner(original, "soiree-ab")
    assert partnered and link.startswith(affiliation.AWIN)
    assert {k: v for k, v in query(link).items() if k != "ued"} == {"awinmid": "1234", "awinaffid": "987654", "clickref": "soiree-ab"}
    assert unquote(link.split("&ued=", 1)[1]) == original
    assert affiliation.partner(link, "soiree-ab") == (link, False)  # wrapped once
    # A site Awin does not serve here, a page of the base's own: as they are.
    assert affiliation.partner("https://shotgun.live/fr/events/x", "soiree-ab") == ("https://shotgun.live/fr/events/x", False)
    assert affiliation.partner("/images/x.jpg", "soiree-ab") == ("/images/x.jpg", False)


def test_the_evenings_served_carry_them_and_say_so(monkeypatch):
    monkeypatch.setenv("AWIN_PUBLISHER_ID", "987654")
    monkeypatch.setenv("AWIN_MERCHANTS", "billetweb.fr:4321")  # the test activities' booking site
    req, _, route = _night()
    page = parcours.soiree_json("soiree-ab", {"routes": [route], "requests": [req]})
    steps = page["routes"][0]["steps"]
    booked = [s for s in steps if s["booking_action"] == "reserver"]
    assert booked and all(s["partner"] and query(s["booking_url"])["clickref"] == "soiree-ab" for s in booked)
    # A bar walked into: its own site, no partner.
    assert all(not s["partner"] for s in steps if s["booking_action"] == "voir_lieu")
    # Without the evening's page, the links as collected.
    assert not any(s["partner"] for s in parcours.route_json(0, route, req)["steps"])
