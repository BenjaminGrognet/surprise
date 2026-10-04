import pytest

from surprise import availability, enrich, parcours


@pytest.fixture(autouse=True)
def images_show(monkeypatch):
    """Evenings are composed without asking the test images' sites whether they answer (see test_parcours)."""
    monkeypatch.setattr(parcours, "unshown", lambda steps: set())


@pytest.fixture(autouse=True)
def nominatim_asked_afresh(monkeypatch):
    """No test reads an answer of Nominatim kept by another one (surprise.enrich._kept)."""
    monkeypatch.setattr(enrich, "_answers", {})
    monkeypatch.setattr(enrich, "_new_answers", {})


@pytest.fixture(autouse=True)
def funbooker_unpaced(monkeypatch):
    """Funbooker's listings are read one per second at collection (surprise.availability): not in the tests."""
    monkeypatch.setattr(availability, "FUNBOOKER_LISTING_DELAY", 0)
