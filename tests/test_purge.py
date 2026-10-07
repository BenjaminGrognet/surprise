import json
from datetime import date

from surprise.local_store import LocalStore
from surprise.purge import past_activities

TODAY = date(2026, 10, 7)


def _fiche(kind: str = "permanent", **dates) -> str:
    return json.dumps({"title": "x", "kind": kind, "occurrences": [], **dates})


def test_past_activities_go_unless_a_history_holds_them(tmp_path):
    rows = {
        "concert-hier": _fiche("temporary", occurrences=[{"starts_at": "2026-10-06T19:00:00Z"}]),
        "concert-ce-soir": _fiche("temporary", occurrences=[{"starts_at": "2026-10-07T19:00:00Z"}]),
        # Sessions gone, but its run goes on: collected again, it gets its new ones.
        "piece-en-cours": _fiche("temporary", ends_on="2026-12-31", occurrences=[{"starts_at": "2026-10-01T19:00:00Z"}]),
        "expo-finie": _fiche("temporary", starts_on="2026-09-01", ends_on="2026-10-06"),
        "bar": _fiche(starts_on="2019-05-01"),  # a place's opening day is no end
        "garde-par-une-soiree": _fiche("temporary", ends_on="2026-10-01"),
        "montree-seulement": _fiche("temporary", ends_on="2026-10-01"),
    }
    with LocalStore(tmp_path / "s.db") as store:
        store._run_many(
            "insert into normalized (source_id, external_id, content_hash, activity, rejection) values ('s', ?, 'h', ?, ?)",
            [(key, fiche, None) for key, fiche in rows.items()] + [("article-passe", None, "sans lieu · passé")],
        )
        store._run_many("insert into raw_records (source_id, external_id, payload, content_hash, fetched_at) values ('s', ?, '{}', 'h', 'x')",
                        [(key,) for key in [*rows, "article-passe"]])
        store._run("insert into soirees (id, requests, chosen_at) values ('choisie', '[]', '2026-09-30'), ('brouillon', '[]', null)")
        store._run_many(
            "insert into soiree_steps (soiree_id, route, position, source_id, external_id, starts_at, ends_at, step) values (?, 0, 0, 's', ?, '', '', '{}')",
            [("choisie", "garde-par-une-soiree"), ("brouillon", "montree-seulement")],
        )

        gone = past_activities(store, TODAY)
        assert sorted(key for _, key in gone) == ["article-passe", "concert-hier", "expo-finie", "montree-seulement"]
        store.delete_activities(gone)
        left = {key for _, key, *_ in store.activities_with_rejection()}
        assert left == {"concert-ce-soir", "piece-en-cours", "bar", "garde-par-une-soiree"}
        assert {key for (key,) in store._run("select external_id from raw_records")} == left
        # The draft that showed it loses that step; the chosen evening keeps its own.
        assert store._run("select soiree_id from soiree_steps").fetchall() == [("choisie",)]
