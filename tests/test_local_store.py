import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from surprise.collectors import que_faire_a_paris as qfap
from surprise.local_store import LocalStore

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "que_faire_a_paris.json").read_text())
NOW = datetime(2026, 9, 24, 22, tzinfo=timezone.utc)


def test_raw_records_are_deduplicated(tmp_path):
    path = tmp_path / "surprise.db"
    records = [qfap.to_raw_record(p) for p in FIXTURE]
    with LocalStore(path) as store:
        assert store.save_raw_records(records) == 4
        assert store.save_raw_records(records) == 0
        changed = qfap.to_raw_record({**FIXTURE[0], "title": "Nouveau titre"})
        assert store.save_raw_records([changed]) == 1


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
