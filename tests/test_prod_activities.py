"""The tests' activities, the project's (tests/prod_activities.py): read at most every FRESH_HOURS, those last read
kept when the base cannot be reached, never without them."""

import os
import pickle
import time
from datetime import date

import pytest

import prod_activities


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """The copy kept, in a folder of the test's own; the project's base out of reach."""
    path = tmp_path / "data" / "tests" / "activites-prod.pickle"
    monkeypatch.setattr(prod_activities, "CACHE", path)
    monkeypatch.setattr(prod_activities, "ROOT", tmp_path)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("SURPRISE_PROD_REFRESH", raising=False)
    return path


def _keep(path, items, hours_ago=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps((items, {})))
    then = time.time() - hours_ago * 3600
    os.utime(path, (then, then))


def test_the_day_is_the_next_friday_as_the_app_proposes():
    assert prod_activities.next_friday(date(2026, 10, 8)) == date(2026, 10, 9)  # a Thursday
    assert prod_activities.next_friday(date(2026, 10, 9)) == date(2026, 10, 16)  # a Friday: the next one


def test_the_base_address_comes_from_the_environment_or_dotenv(cache, monkeypatch):
    assert prod_activities.db_url() is None
    (cache.parents[2] / ".env").write_text('ANTHROPIC_API_KEY=x\nSUPABASE_DB_URL="postgresql://lecture@pooler/postgres"\n', encoding="utf-8")
    assert prod_activities.db_url() == "postgresql://lecture@pooler/postgres"
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://env@pooler/postgres")
    assert prod_activities.db_url() == "postgresql://env@pooler/postgres"


def test_activities_read_lately_are_taken_as_they_are(cache):
    _keep(cache, [{"title": "lu tout à l'heure"}], hours_ago=1)
    assert prod_activities.rows().list_for_moderation() == [{"title": "lu tout à l'heure"}]


def test_older_ones_are_read_again_else_kept_when_the_base_cannot_be_reached(cache, capsys):
    _keep(cache, [{"title": "lu hier"}], hours_ago=prod_activities.FRESH_HOURS + 1)
    assert prod_activities.rows().list_for_moderation() == [{"title": "lu hier"}]
    assert "injoignable" in capsys.readouterr().out


def test_without_any_the_tests_are_told_why(cache):
    with pytest.raises(LookupError, match="SUPABASE_DB_URL"):
        prod_activities.rows()
