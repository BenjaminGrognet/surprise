import pytest

from surprise import parcours


@pytest.fixture(autouse=True)
def images_show(monkeypatch):
    """Evenings are composed without asking the test images' sites whether they answer (see test_parcours)."""
    monkeypatch.setattr(parcours, "unshown", lambda steps: set())
