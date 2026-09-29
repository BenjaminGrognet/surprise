import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from surprise.collectors import que_faire_a_paris as qfap
from surprise.local_store import LocalStore, copy, open_store

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "que_faire_a_paris.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 9, 24, 22, tzinfo=timezone.utc)


def test_raw_records_are_deduplicated(tmp_path):
    path = tmp_path / "surprise.db"
    records = [qfap.to_raw_record(p) for p in FIXTURE]
    with LocalStore(path) as store:
        store.save_raw_records(records)
        store.save_raw_records(records)  # read again unchanged: only its fetch time moves
        changed = qfap.to_raw_record({**FIXTURE[0], "title": "Nouveau titre"})
        store.save_raw_records([changed])
    assert sqlite3.connect(path).execute("select count(*) from raw_records").fetchone() == (5,)


def test_fresh_pages_are_not_read_again(tmp_path):
    from surprise.collectors import common

    calls = []

    def read():
        calls.append(1)
        return {"id": "12345", "title": "Concert"}

    common._fresh.clear()
    [payload] = common.remembered("https://site.example/a", read)
    assert payload["_page"] == "https://site.example/a" and calls == [1]
    raw = qfap.to_raw_record(FIXTURE[0] | {"_page": "https://site.example/a"})
    assert raw.content_hash == qfap.to_raw_record(FIXTURE[0]).content_hash  # bookkeeping is not content
    with LocalStore(tmp_path / "s.db") as store:
        result = qfap.normalize(raw.payload, NOW)
        store.save_raw_records([result.raw])
        store.save_normalized([(result.raw, result.activity, result.rejection)])
        common._fresh.update(store.fresh_pages("que_faire_a_paris"))
        assert store.fresh_pages("que_faire_a_paris", days=0) == {}
    [stored] = common.remembered("https://site.example/a", read)
    assert stored["_cached"] and calls == [1]
    # Modified since it was read (sitemap lastmod): read again.
    common.remembered("https://site.example/a", read, modified="2026-09-30")
    assert calls == [1, 1]
    common._fresh.clear()


def test_page_checks_are_kept(tmp_path):
    with LocalStore(tmp_path / "s.db") as store:
        store.save_page_checks({"https://club.example/": ("billetterie du lieu", False), "https://ferme.example/": (None, True)})
        assert store.page_checks() == {"https://club.example/": ("billetterie du lieu", False), "https://ferme.example/": (None, True)}
        assert store.page_checks(days=-1) == {}


def test_latest_normalization_is_kept(tmp_path):
    path = tmp_path / "surprise.db"
    results = [qfap.normalize(p, NOW) for p in FIXTURE]
    with LocalStore(path) as store:
        store.save_normalized([(r.raw, r.activity, r.rejection) for r in results])
        store.save_normalized([(r.raw, r.activity, r.rejection) for r in results])
    rows = dict(sqlite3.connect(path).execute("select external_id, coalesce(rejection, activity) from normalized"))
    assert len(rows) == 4
    assert rows["2"] == "jeune public"
    assert json.loads(rows["12345"])["venue"]["arrondissement"] == 5


def _store_with_fixture(path):
    results = [qfap.normalize(p, NOW) for p in FIXTURE]
    store = LocalStore(path)
    store.save_raw_records([r.raw for r in results])
    store.save_normalized([(r.raw, r.activity, r.rejection) for r in results])
    return store, results


def test_moderation_lists_kept_activities_as_proposed(tmp_path):
    store, _ = _store_with_fixture(tmp_path / "surprise.db")
    with store:
        items = {i["external_id"]: i for i in store.list_for_moderation()}
    assert set(items) == {"12345", "4"}
    assert items["12345"]["status"] == "proposed"
    assert items["12345"]["activity"]["venue"]["arrondissement"] == 5
    assert items["12345"]["source_url"] == str(qfap.to_raw_record(FIXTURE[0]).url)


def test_moderation_decision_survives_recollection_and_flags_changes(tmp_path):
    store, results = _store_with_fixture(tmp_path / "surprise.db")
    with store:
        assert store.set_status("que_faire_a_paris", "12345", "approved")
        store.save_normalized([(r.raw, r.activity, r.rejection) for r in results])
        [item] = [i for i in store.list_for_moderation() if i["external_id"] == "12345"]
        assert (item["status"], item["changed_since_decision"]) == ("approved", False)

        changed = qfap.normalize({**FIXTURE[0], "title": "Nouveau titre"}, NOW)
        store.save_normalized([(changed.raw, changed.activity, changed.rejection)])
        [item] = [i for i in store.list_for_moderation() if i["external_id"] == "12345"]
        assert (item["status"], item["changed_since_decision"]) == ("approved", True)

        assert store.set_status("que_faire_a_paris", "12345", "proposed")
        [item] = [i for i in store.list_for_moderation() if i["external_id"] == "12345"]
        assert item["status"] == "proposed"


def test_moderation_rejects_unknown_or_filtered_activities(tmp_path):
    store, _ = _store_with_fixture(tmp_path / "surprise.db")
    with store:
        assert not store.set_status("que_faire_a_paris", "inconnu", "approved")
        assert not store.set_status("que_faire_a_paris", "2", "approved")  # rejected by the hard filters
        with pytest.raises(ValueError):
            store.set_status("que_faire_a_paris", "12345", "published")


def test_enrichment_is_listed_and_survives_recollection(tmp_path):
    store, results = _store_with_fixture(tmp_path / "surprise.db")
    with store:
        assert {i["external_id"] for i in store.pending_enrichment()} == {"12345", "4"}
        store.save_enrichment("que_faire_a_paris", "4", {"image_url": "https://site.example/a.jpg", "site_excerpt": "Extrait"})
        store.save_normalized([(r.raw, r.activity, r.rejection) for r in results])
        assert {i["external_id"] for i in store.pending_enrichment()} == {"12345"}
        # Enriched without a description: picked up again once descriptions are enabled.
        assert {i["external_id"] for i in store.pending_enrichment(missing_description=True)} == {"12345", "4"}
        [item] = [i for i in store.list_for_moderation() if i["external_id"] == "4"]
    assert item["enrichment"]["image_url"] == "https://site.example/a.jpg"
    assert item["enrichment"]["description"] is None


def test_activities_rejected_at_collection_are_listed_apart(tmp_path):
    store, results = _store_with_fixture(tmp_path / "surprise.db")
    kept = next(r for r in results if r.raw.external_id == "12345")
    with store:
        store.save_normalized([(kept.raw, kept.activity, "ni gratuit ni réservable en ligne")])
        items = {i["external_id"]: i for i in store.list_for_moderation()}
        pending = {i["external_id"] for i in store.pending_enrichment()}
        # A moderator can still keep it.
        assert store.set_status("que_faire_a_paris", "12345", "approved")
        approved = {i["external_id"]: i["status"] for i in store.list_for_moderation()}
        pending_after = {i["external_id"] for i in store.pending_enrichment()}
    assert (items["12345"]["status"], items["12345"]["rejection"]) == ("filtered", "ni gratuit ni réservable en ligne")
    assert "12345" not in pending
    assert approved["12345"] == "approved"
    assert "12345" in pending_after


def test_availability_cache(tmp_path):
    with LocalStore(tmp_path / "s.db") as store:
        store.save_availability("wecandoo", "a", "2026-10-09", 2, "Wecandoo", True, ["19:00-21:00"], "")
        store.save_availability("fever", "b", "2026-10-09", 2, None, None, [], "sans moteur")
        cached = store.cached_availability("2026-10-09", 2, max_age_hours=6)
        assert cached[("wecandoo", "a")] == {"engine": "Wecandoo", "available": True, "slots": ["19:00-21:00"], "detail": ""}
        assert cached[("fever", "b")]["engine"] is None
        assert store.cached_availability("2026-10-10", 2, max_age_hours=6) == {}


def test_copy_adds_only_missing_rows(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    source, _ = _store_with_fixture(tmp_path / "a.db")
    with source, open_store(tmp_path / "b.db") as target:
        source.set_status("que_faire_a_paris", "12345", "approved")
        source.save_enrichment("que_faire_a_paris", "12345", {"image_url": "https://example.com/a.jpg"})
        assert isinstance(target, LocalStore)
        assert copy(source, target) == {"raw_records": 4, "normalized": 4, "moderation": 1, "enrichment": 1, "keywords": 0}
        assert set(copy(source, target).values()) == {0}
        assert target.list_for_moderation() == source.list_for_moderation()
