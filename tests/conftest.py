import pytest

from surprise import availability, enrich, images, parcours


@pytest.fixture(autouse=True)
def images_show(monkeypatch):
    """Evenings are composed with the photo filters, without asking the test images' sites whether they answer (see
    test_parcours)."""
    monkeypatch.setattr(parcours, "IMAGE_FILTERS", True)
    monkeypatch.setattr(parcours, "unshown", lambda steps: set())


@pytest.fixture(autouse=True)
def images_kept_aside(monkeypatch, tmp_path):
    """A kept evening's images are not downloaded (see test_images), nor any copied into data/images."""
    monkeypatch.setattr(parcours, "keep_images", lambda route: None)
    monkeypatch.setattr(images, "DIRECTORY", tmp_path / "images")


@pytest.fixture(autouse=True)
def nominatim_asked_afresh(monkeypatch):
    """No test reads an answer of Nominatim kept by another one (surprise.enrich._kept)."""
    monkeypatch.setattr(enrich, "_answers", {})
    monkeypatch.setattr(enrich, "_new_answers", {})


@pytest.fixture(autouse=True)
def funbooker_unpaced(monkeypatch):
    """Funbooker's listings are read one per second at collection (surprise.availability): not in the tests."""
    monkeypatch.setattr(availability, "FUNBOOKER_LISTING_DELAY", 0)


@pytest.fixture(autouse=True)
def no_real_relay(monkeypatch):
    """The project's .env (read by `import surprise`) may hold a real SMTP relay and Firebase account: no test sends
    through them; those that send give their own, fake."""
    for key in ("SMTP_URL", "MAIL_FROM", "FIREBASE_SERVICE_ACCOUNT"):
        monkeypatch.delenv(key, raising=False)
