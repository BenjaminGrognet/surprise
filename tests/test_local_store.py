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


def test_limit_counts_only_pages_read():
    from surprise.collectors.common import up_to_new

    raw = qfap.to_raw_record(FIXTURE[0])
    cached = qfap.normalize(raw.payload | {"_cached": True}, NOW)
    fresh = qfap.normalize(raw.payload, NOW)
    pulled = []

    def results():
        for result in [cached, cached, fresh, cached, fresh, fresh]:
            pulled.append(result)
            yield result

    assert len(list(up_to_new(results(), 2))) == 5
    assert len(pulled) == 5  # the page after the last one is never asked for
    assert list(up_to_new(results(), 0)) == [] and len(list(up_to_new(results(), None))) == 6


def test_page_checks_are_kept(tmp_path):
    with LocalStore(tmp_path / "s.db") as store:
        store.save_page_checks({"https://club.example/": ("billetterie du lieu", False), "https://ferme.example/": (None, True)})
        assert store.page_checks() == {"https://club.example/": ("billetterie du lieu", False), "https://ferme.example/": (None, True)}
        assert store.page_checks(days=-1) == {}


def test_osm_places_are_kept_found_or_not(tmp_path):
    with LocalStore(tmp_path / "s.db") as store:
        store.save_osm_places({("Dipsy", "75006"): {"latitude": 48.85}, ("Nulle part", "75001"): None})
        assert store.osm_places() == {("Dipsy", "75006"): {"latitude": 48.85}, ("Nulle part", "75001"): None}
        assert store.osm_places(days=-1) == {}


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


def _step(external_id, position=0, start="20:00"):
    return (0, position, "que_faire_a_paris", external_id, f"2026-10-09T{start}+02:00", "2026-10-09T23:00+02:00", False, "{}")


def test_a_redraw_keeps_the_replaced_steps(tmp_path):
    with LocalStore(tmp_path / "s.db") as store:
        store.save_soiree("soiree-a", "[]", 0, [(0, None, "Titre", "Pitch", 1.0)], [_step("bar"), _step("club", 1)])
        # The bar gives way to a show; the club stays, later.
        store.save_soiree("soiree-a", "[]", 0, [(0, None, "Titre", "Pitch", 1.0)], [_step("show"), _step("club", 1, "21:00")])
        saved = store.soiree("soiree-a")
        history = store._run(
            "select external_id, starts_at, replaced_at is not null from soiree_steps order by id"
        ).fetchall()
    assert [step for _, _, step in saved["steps"]] == ["{}", "{}"]
    assert set(saved["seen"]) == {("que_faire_a_paris", "bar"), ("que_faire_a_paris", "club"), ("que_faire_a_paris", "show")}
    assert history == [("bar", "2026-10-09T20:00+02:00", 1), ("club", "2026-10-09T21:00+02:00", 0), ("show", "2026-10-09T20:00+02:00", 0)]


def test_copy_adds_only_missing_rows(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    source, _ = _store_with_fixture(tmp_path / "a.db")
    with source, open_store(tmp_path / "b.db") as target:
        source.set_status("que_faire_a_paris", "12345", "approved")
        source.save_enrichment("que_faire_a_paris", "12345", {"image_url": "https://example.com/a.jpg"})
        source.save_soiree("soiree-a", "[]", 0, [(0, None, "Titre", "Pitch", 1.0)], [_step("12345")])
        assert isinstance(target, LocalStore)
        assert copy(source, target) == {
            "raw_records": 4, "normalized": 4, "moderation": 1, "enrichment": 1, "keywords": 0, "osm_places": 0,
            "profiles": 0, "soirees": 1, "soiree_routes": 1, "soiree_steps": 1,
        }
        assert target.soiree("soiree-a") == source.soiree("soiree-a") and target.soiree("absente") is None
        assert set(copy(source, target).values()) == {0}
        assert target.list_for_moderation() == source.list_for_moderation()
