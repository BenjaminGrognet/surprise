import json
from datetime import date, datetime, timedelta

import pytest

from surprise import availability, parcours
from surprise.local_store import open_store
from surprise.parcours import PARIS, Request

DAY = date(2026, 10, 9)  # a Friday


def at(hour, minute=0, day=DAY):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=PARIS)


def request(**extra):
    start, end = parcours.window(DAY, "19:00", "00:30")
    return Request(**{"day": DAY, "budget": 150, "start": start, "end": end, "vibes": ["rire", "romantique"], **extra})


def item(external_id, title, categories, *, occurrences=(), price=20, free=False, lat=48.86, lon=2.35, kind="temporary", venue=None, hours=None):
    return {
        "source_id": "test",
        "external_id": external_id,
        "status": "proposed",
        "source_url": f"https://example.org/{external_id}",
        "lead_text": None,
        "activity": {
            "title": title,
            "kind": kind,
            "categories": categories,
            "duration_minutes": None,
            "occurrences": [{"starts_at": o.isoformat(), "ends_at": None} for o in occurrences],
            "offers": [{"is_free": free, "price_min": None if free else price, "price_unit": "per_person",
                        "booking_url": None if free else f"https://www.billetweb.fr/{external_id}"}],
            "venue": {"name": venue or title, "arrondissement": 3, "latitude": lat, "longitude": lon},
            "image": {"url": f"https://example.org/{external_id}.jpg"},
        },
        "enrichment": {"image_url": None, "booking_url": None, "opening_hours": hours, "latitude": None, "longitude": None, "description": None},
    }


def test_window_ends_the_next_morning():
    start, end = parcours.window(DAY, "19:00", "00:30")
    assert (start, end) == (at(19), at(0, 30, date(2026, 10, 10)))


def test_opening_hours():
    assert parcours.opening_intervals("Mo-Su 12:00-23:00", DAY) == [(at(12), at(23))]
    assert parcours.opening_intervals("We-Sa 12:00-13:30, 19:00-21:30; Tu 19:00-21:30", DAY) == [(at(12), at(13, 30)), (at(19), at(21, 30))]
    assert parcours.opening_intervals("Mo-Th 18:00-02:00; Fr off", DAY) == []
    assert parcours.opening_intervals("Tu-Sa 18:00-02:00", DAY) == [(at(18), at(2, 0, date(2026, 10, 10)))]
    assert parcours.opening_intervals("sunrise-sunset", DAY) is None


def test_travel_on_foot_then_by_metro():
    assert parcours.travel_minutes(0.8) == 14
    assert parcours.travel_minutes(1.0) == 17 and parcours.travel_minutes(4) == 28


def test_dated_show_only_on_its_evening():
    show = item("show", "Stand-up", ["humour"], occurrences=[at(20)])
    other_day = item("other", "Stand-up", ["humour"], occurrences=[at(20) + timedelta(days=1)])
    run = item("run", "Pièce", ["theatre"])  # a run without its evenings
    candidate = parcours.build_candidate(show, request(), None)
    assert candidate.starts == [at(20)] and candidate.kind == "seance" and candidate.price == 40
    assert parcours.build_candidate(other_day, request(), None) is None
    assert parcours.build_candidate(run, request(), None) is None


def test_checked_slots_and_walk_in_bars():
    workshop = item("atelier", "Atelier bougie", ["atelier"], kind="permanent")
    checked = {"engine": "Wecandoo", "available": True, "slots": ["10:00-12:00", "19:30-21:30"], "detail": ""}
    candidate = parcours.build_candidate(workshop, request(), checked)
    assert candidate.starts == [at(19, 30)] and candidate.end_of(at(19, 30)) == at(21, 30)
    assert parcours.build_candidate(workshop, request(), {**checked, "available": False}) is None

    bar = item("bar", "Bar à cocktails", ["bar"], kind="permanent", hours="Mo-Su 18:00-02:00")
    candidate = parcours.build_candidate(bar, request(), None)
    assert candidate.kind == "sans_resa" and candidate.flexible and candidate.starts[0] == at(19)
    assert parcours.build_candidate(bar, request(walk_in=False), None) is None
    restaurant = item("resto", "Bistrot", ["restaurant"], kind="permanent", hours="Mo-Su 19:00-23:00")
    assert parcours.build_candidate(restaurant, request(), None) is None  # a dinner needs a confirmed table


def test_the_checks_are_spread_over_the_engines_and_saved_at_once(monkeypatch):
    def workshop(engine, n):
        found = item(f"{engine}{n}", f"Atelier {n}", ["atelier"], kind="permanent")
        found["activity"]["booking"] = {"mode": "creneau", "engine": engine, "check": f"{engine}:{n}"}
        return found

    class Store:
        saved = []

        def cached_availability(self, day, party, max_age_hours):
            return {}

        def save_availabilities(self, answers):
            self.saved.append(answers)

    items = [workshop("funbooker", n) for n in range(8)] + [workshop("wecandoo", n) for n in range(3)] + [workshop("come_to_paris", n) for n in range(3)]
    prescore = {(i["source_id"], i["external_id"]): -n for n, i in enumerate(items)}
    asked = []
    monkeypatch.setattr(parcours.availability, "check", lambda client, item, day, party: asked.append(item["external_id"]) or (
        "Funbooker", parcours.availability.Availability(True, ["20:00"]),
    ))
    store = Store()
    checked = parcours.check_engines(store, items, request(), 30, prescore)
    # The best 5 of an engine, whose site is asked every half second, then the other engines'; Come to Paris,
    # asked 3 or 4 times a check, 2.
    assert sorted(asked) == sorted([f"funbooker{n}" for n in range(5)] + [f"wecandoo{n}" for n in range(3)] + ["come_to_paris0", "come_to_paris1"])
    assert set(checked) == {("test", name) for name in asked}
    assert [len(answers) for answers in store.saved] == [10]


def test_routes_chain_in_time_and_place_and_do_not_share_steps():
    items = [
        item("a", "Comedy club", ["humour"], occurrences=[at(19, 30)], venue="Club"),
        item("b", "Concert aux chandelles", ["concert"], occurrences=[at(21, 30)], lat=48.865, venue="Église"),
        item("c", "Croisière romantique", ["croisiere"], occurrences=[at(19)], lat=48.858, lon=2.34, venue="Quai"),
        item("d", "Stand-up du soir", ["humour"], occurrences=[at(21, 15)], lat=48.859, lon=2.341, venue="Cave"),
        item("far", "Comédie en banlieue", ["humour"], occurrences=[at(21, 30)], lat=48.95, lon=2.5, venue="Loin"),
        item("bar", "Bar caché", ["bar"], kind="permanent", hours="Mo-Su 18:00-02:00", lat=48.861, venue="Bar"),
    ]
    req = request()
    candidates = []
    for entry in items:
        candidate = parcours.build_candidate(entry, req, None)
        candidate.score = parcours.score(candidate, req)
        candidates.append(candidate)
    routes = parcours.pick(parcours.compose(candidates, req))
    assert routes
    for route in routes:
        for previous, step in zip(route.steps, route.steps[1:]):
            assert step.start >= previous.end + timedelta(minutes=step.travel)
            assert step.travel <= 35
        assert "far" not in {s.candidate.key[1] for s in route.steps}
        # never two stand-ups in one evening
        assert sum("stand_up" in s.candidate.tags for s in route.steps) <= 1
    keys = [s.candidate.key for route in routes for s in route.steps]
    assert len(keys) == len(set(keys))


def test_budget_is_a_ceiling():
    items = [
        item("a", "Comedy club", ["humour"], occurrences=[at(19, 30)], price=100, venue="Club"),
        item("b", "Concert aux chandelles", ["concert"], occurrences=[at(21, 30)], price=100, venue="Église"),
    ]
    req = request(budget=100)
    candidates = [parcours.build_candidate(entry, req, None) for entry in items]
    for candidate in candidates:
        candidate.score = parcours.score(candidate, req)
    assert parcours.compose(candidates, req) == []


def test_each_step_has_its_booking_link():
    req = request()
    candidates = [
        parcours.build_candidate(item("a", "Comedy club", ["humour"], occurrences=[at(19, 30)], venue="Club"), req, None),
        parcours.build_candidate(item("b", "Concert aux chandelles", ["concert"], occurrences=[at(21, 30)], venue="Église"), req, None),
    ]
    route = parcours.Route([parcours.Step(candidates[0], at(19, 30), at(21)), parcours.Step(candidates[1], at(21, 30), at(23), travel=5, distance=0.3)])
    parcours.name_by_rules(route, req)
    steps = parcours.route_json(0, route)["steps"]
    assert [s["booking_action"] for s in steps] == ["reserver", "reserver"] and steps[0]["booking_url"] == "https://www.billetweb.fr/a"
    assert "Séance de 21:30" in steps[1]["basis"] and steps[1]["redo"] == "routes/0/steps/1"


def test_trame_orders_the_steps_and_lets_the_bar_end_early():
    req = request(vibes=["insolite", "fete"], trame=["apero", "insolite", "fete"], end=at(4, 0, date(2026, 10, 10)))
    items = [
        item("bar", "Bar à cocktails", ["bar"], kind="permanent", hours="Mo-Su 18:00-02:00", venue="Bar"),
        item("club", "Soirée techno", ["nuit"], occurrences=[at(23)], lat=48.862, venue="Club"),
        item("immersif", "Expérience immersive", ["lieu_insolite"], occurrences=[at(20, 15)], lat=48.861, venue="Salle"),
    ]
    candidates = []
    for entry in items:
        candidate = parcours.build_candidate(entry, req, None)
        candidate.score = parcours.score(candidate, req)
        candidates.append(candidate)
    [route] = parcours.pick(parcours.compose(candidates, req), 3)
    assert [s.candidate.key[1] for s in route.steps] == ["bar", "immersif", "club"]
    bar, show, club = route.steps
    # The bar is left in time for the show, after 45 minutes at least.
    assert bar.end - bar.start >= timedelta(minutes=45) and bar.end + timedelta(minutes=show.travel) <= show.start
    assert club.start == at(23)


def _scored(entries, req):
    candidates = []
    for entry in entries:
        candidate = parcours.build_candidate(entry, req, None)
        candidate.score = parcours.score(candidate, req)
        candidates.append(candidate)
    return candidates


def _night():
    req = request(vibes=["insolite", "fete"], trame=["apero", "insolite", "fete"], end=at(4, 0, date(2026, 10, 10)))
    entries = [
        item("bar", "Bar à cocktails", ["bar"], kind="permanent", hours="Mo-Su 18:00-02:00", venue="Bar"),
        item("club", "Soirée techno", ["nuit"], occurrences=[at(23)], lat=48.862, venue="Club"),
        item("immersif", "Expérience immersive", ["lieu_insolite"], occurrences=[at(20, 15)], lat=48.861, venue="Salle"),
        item("autre", "Parcours sensoriel dans le noir", ["lieu_insolite"], occurrences=[at(21)], lat=48.8615, venue="Noir"),
        item("loin", "Expérience lointaine", ["lieu_insolite"], occurrences=[at(21)], lat=48.95, lon=2.5, venue="Loin"),
    ]
    candidates = _scored(entries, req)
    [route] = parcours.pick(parcours.compose([c for c in candidates if c.key[1] != "autre"], req), 1)
    return req, candidates, route


def test_one_step_is_replaced_and_the_evening_still_chains():
    req, candidates, route = _night()
    assert route.steps[1].candidate.key[1] == "immersif"
    steps = parcours.replace_step(route, 1, candidates, req, {("test", "immersif")})
    assert [s.candidate.key[1] for s in steps] == ["bar", "autre", "club"]
    bar, show, club = steps
    # The bar stays longer before the later show; the club is kept.
    assert bar.end + timedelta(minutes=show.travel) <= show.start and bar.end > route.steps[0].end
    assert show.start == at(21) and club.start == at(23) and show.end + timedelta(minutes=club.travel) <= club.start
    # Nothing else of its kind nearby: no replacement.
    assert parcours.replace_step(route, 1, candidates, req, {("test", "immersif"), ("test", "autre")}) is None


def test_regenerate_rewrites_the_saved_state(tmp_path, monkeypatch):
    req, candidates, route = _night()
    monkeypatch.setattr(parcours, "DB", tmp_path / "s.db")
    monkeypatch.setattr(parcours, "candidates_for", lambda store, base, request, checks: candidates)
    parcours.name_by_rules(route, req)
    route.request = req
    parcours.save("essai", {"routes": [route], "requests": [req], "seen": {s.candidate.key for s in route.steps}})
    assert parcours.soiree_json("essai", parcours.load("essai"))["routes"][0]["steps"][1]["redo"] == "routes/0/steps/1"

    assert parcours.regenerate(None, None, "essai", 0, 1, claude=False) is None
    state = parcours.load("essai")
    assert [s.candidate.key[1] for s in state["routes"][0].steps] == ["bar", "autre", "club"]
    # The store links the evening to its activities, as redrawn, and keeps the one replaced.
    with open_store(tmp_path / "s.db") as store:
        rows = store._run(
            "select position, external_id, replaced_at is not null from soiree_steps where soiree_id = 'essai' order by id"
        ).fetchall()
    assert rows == [(0, "bar", 0), (1, "immersif", 1), (2, "club", 0), (1, "autre", 0)]
    assert parcours.load("essai")["routes"][0].steps[1].start.tzinfo == parcours.PARIS
    assert ("test", "autre") in state["seen"]
    assert parcours.soiree_json("essai", state)["routes"][0]["steps"][1]["title"] == "Parcours sensoriel dans le noir"
    # The only other evening would repeat a step: the whole route has no other draw (from the candidates kept by the first redraw).
    base = parcours.Base([c.item for c in candidates], {c.key: 35 for c in candidates})
    assert parcours.regenerate(None, base, "essai", 0, claude=False) == "aucun autre parcours complet ce soir-là"
    assert parcours.regenerate(None, base, "absent", 0, claude=False) == "parcours introuvable : relancez la composition"


def test_a_step_changed_again_is_looked_for_on_the_server(tmp_path, monkeypatch):
    """Every activity kept that would do was proposed: the engines are asked for others, rather than going round."""
    req, candidates, route = _night()
    monkeypatch.setattr(parcours, "DB", tmp_path / "s.db")
    route.request = req
    parcours.save("essai", {"routes": [route], "requests": [req], "seen": set()}, candidates=[candidates])
    workshop = item("atelier", "Atelier secret", ["lieu_insolite"], kind="permanent", lat=48.8612, venue="Atelier")
    workshop["activity"]["booking"] = {"check": "wecandoo:atelier"}
    base = parcours.Base([c.item for c in candidates] + [workshop], {**{c.key: 35 for c in candidates}, ("test", "atelier"): 35})
    asked = []

    def check(client, entry, day, party):
        asked.append(entry["external_id"])
        return "wecandoo", availability.Availability(True, ["21:00-22:15"])

    monkeypatch.setattr(parcours.availability, "check", check)
    assert parcours.regenerate(None, base, "essai", 0, 1, claude=False) is None
    assert parcours.load("essai")["routes"][0].steps[1].candidate.key == ("test", "autre") and asked == []
    # Both nearby experiences shown: the workshop, checked now, rather than the first one again.
    assert parcours.regenerate(None, base, "essai", 0, 1, claude=False) is None
    assert parcours.load("essai")["routes"][0].steps[1].candidate.key == ("test", "atelier") and asked == ["atelier"]
    with open_store(tmp_path / "s.db") as store:
        kept = store.soiree_candidates("essai", 0, parcours.CACHE_HOURS)
    assert ("test", "atelier") in {c.key for c in parcours._candidates_from(kept, base)}
    # Nothing left to check: no activity shown before comes back.
    assert parcours.regenerate(None, base, "essai", 0, 1, claude=False) == "plus d'autre activité qui s'enchaîne à cette étape ce soir-là"
    assert asked == ["atelier"]


def _three_routes(tmp_path, monkeypatch):
    """An evening composed with three routes, saved with its candidates."""
    req = request(vibes=["insolite", "fete"], trame=["apero", "insolite"])
    entries = [
        item("bar", "Bar à cocktails", ["bar"], kind="permanent", hours="Mo-Su 18:00-02:00", venue="Bar"),
        item("cave", "Cave à vins", ["bar"], kind="permanent", hours="Mo-Su 18:00-02:00", lat=48.87, venue="Cave"),
        item("pub", "Pub irlandais", ["bar"], kind="permanent", hours="Mo-Su 18:00-02:00", lat=48.85, venue="Pub"),
        item("immersif", "Expérience immersive", ["lieu_insolite"], occurrences=[at(20, 15)], lat=48.861, venue="Salle"),
        item("noir", "Parcours sensoriel dans le noir", ["lieu_insolite"], occurrences=[at(20, 30)], lat=48.869, venue="Noir"),
        item("illusions", "Musée des illusions", ["lieu_insolite"], occurrences=[at(20, 30)], lat=48.851, venue="Illusions"),
        item("autre", "Expérience secrète", ["lieu_insolite"], occurrences=[at(21)], lat=48.8605, venue="Secret"),
    ]
    candidates = _scored(entries, req)
    base = parcours.Base(entries, {c.key: 35 for c in candidates})
    monkeypatch.setattr(parcours, "DB", tmp_path / "s.db")
    routes = parcours.pick([r for r in parcours.compose(candidates, req) if r.steps[1].candidate.key[1] != "autre"], 3)
    for route in routes:
        route.request = req
    state = {"routes": routes, "requests": [req], "seen": {s.candidate.key for r in routes for s in r.steps}}
    parcours.save("essai", state, candidates=[candidates])
    return req, base, routes


def test_a_redraw_starts_from_the_candidates_kept_at_the_composition(tmp_path, monkeypatch):
    req, base, routes = _three_routes(tmp_path, monkeypatch)
    assert len(routes) == 3

    def never(*args):
        raise AssertionError("the base is not read again")

    monkeypatch.setattr(parcours, "candidates_for", never)
    assert parcours.regenerate(None, base, "essai", 0, 1, claude=False) is None
    assert parcours.load("essai")["routes"][0].steps[1].candidate.key == ("test", "autre")
    # A candidate kept, its activity rejected since (out of the base): not drawn again.
    with open_store(tmp_path / "s.db") as store:
        kept = store.soiree_candidates("essai", 0, parcours.CACHE_HOURS)
    assert {c.key[1] for c in parcours._candidates_from(kept, base)} == {e["external_id"] for e in base.items}
    smaller = parcours.Base([i for i in base.items if i["external_id"] != "noir"], base.originality)
    assert ("test", "noir") not in {c.key for c in parcours._candidates_from(kept, smaller)}


def test_the_candidates_are_kept_without_their_luck():
    req, candidates, _ = _night()
    drawn = parcours.lucky(candidates)
    assert all(0 <= d.score - c.score <= parcours.VARIETY for c, d in zip(candidates, drawn))
    base = parcours.Base([c.item for c in candidates], {c.key: 35 for c in candidates})
    assert parcours._candidates_from(parcours._candidates_json(candidates), base) == candidates


def test_a_chosen_route_is_the_evenings_only_one(tmp_path, monkeypatch):
    req, base, routes = _three_routes(tmp_path, monkeypatch)
    kept = [s.candidate.key for s in routes[2].steps]
    assert parcours.choose("essai", 2) is None
    state = parcours.load("essai")
    assert state["chosen"] and [[s.candidate.key for s in r.steps] for r in state["routes"]] == [kept]
    page = parcours.soiree_json("essai", state)
    assert page["chosen"] and [r["index"] for r in page["routes"]] == [0] and page["routes"][0]["redo"] == "routes/0"
    with open_store(tmp_path / "s.db") as store:
        assert store.chosen_activities(["essai", "absente"]) == set(kept)
        assert store._run("select count(*) from soiree_steps where soiree_id = 'essai'").fetchone() == (len(kept),)
        assert store.soiree_candidates("essai", 0, parcours.CACHE_HOURS) is None
    # Chosen again (a retry), nothing changes; another route is no more.
    assert parcours.choose("essai", 0) is None and len(parcours.load("essai")["routes"]) == 1
    assert parcours.choose("essai", 1) == "parcours introuvable : relancez la composition"
    # A step changed later is drawn among candidates found anew, checked live.
    found = []
    monkeypatch.setattr(parcours, "candidates_for", lambda store, base_, request_, checks: found.append(checks) or parcours._candidates_from(
        parcours._candidates_json(_scored(base.items, req)), base))
    assert parcours.regenerate(None, base, "essai", 0, 1, checks=10, claude=False) is None
    assert found == [10]


def test_no_stag_party_and_no_late_dinner():
    party = item("evg", "Laser Game formule EVG & EVJF", ["jeu"], occurrences=[at(20)])
    assert parcours.build_candidate(party, request(), None) is None
    restaurant = item("resto", "Bistrot", ["restaurant"], kind="permanent")
    checked = {"engine": "zenchef", "available": True, "slots": ["19:00", "21:30", "22:00", "23:00"], "detail": ""}
    assert parcours.build_candidate(restaurant, request(), checked).starts == [at(19), at(21, 30)]
    late = {**checked, "slots": ["22:30", "23:00"]}
    assert parcours.build_candidate(restaurant, request(), late) is None


def test_claude_titles_come_after_saving(tmp_path, monkeypatch):
    req, _, route = _night()
    monkeypatch.setattr(parcours, "DB", tmp_path / "s.db")
    parcours.name_by_rules(route, req)
    route.request = req
    parcours.save("essai", {"routes": [route], "requests": [req], "seen": set(), "naming": 1})
    assert parcours.load("essai")["naming"] == 1

    def named(routes, request):
        routes[0].title, routes[0].pitch = "Nuit secrète", "Un verre, puis l'inconnu."

    monkeypatch.setattr(parcours, "name_with_claude", named)
    parcours._name_later("essai", [route], req)
    state = parcours.load("essai")
    assert state["routes"][0].title == "Nuit secrète" and state["naming"] == 0


def test_each_site_is_asked_every_half_second_at_most():
    wait = parcours._paced(0.2)
    begin = parcours.clock.monotonic()
    for url in ("https://a.test/1", "https://b.test/1", "https://a.test/2"):
        wait(parcours.httpx.Request("GET", url))
    # a.test waited once; b.test did not have to.
    assert 0.18 <= parcours.clock.monotonic() - begin < 0.35


def test_rules_name_the_evening_by_its_steps_and_place():
    req, _, route = _night()
    parcours.name_by_rules(route, req)
    assert route.title == "Cocktails, immersion et dancefloor dans le Haut-Marais"
    assert route.pitch.startswith("À 19 h, cocktails : « Bar à cocktails » ; puis, à 3 min à pied, immersion : « Expérience immersive » (Salle)")
    assert "et la nuit continue" in route.pitch and route.pitch.endswith("à deux.")
    assert parcours._hour(at(2, 59)) == "3 h" and parcours._hour(at(0, 30)) == "minuit 30" and parcours._hour(at(20, 30)) == "20 h 30"


def test_no_meal_step_when_they_will_have_eaten():
    dinner = item("resto", "Dîner au restaurant", ["restaurant"], occurrences=[at(19, 30)], venue="Resto")
    show = item("show", "Stand-up du vendredi", ["humour"], occurrences=[at(21)], venue="Comedy")
    req = request()
    assert all(c.score > float("-inf") for c in _scored([dinner, show], req))
    hungry_not, _ = _scored([dinner, show], request(no_dinner=True))
    assert hungry_not.role == "repas" and hungry_not.score == float("-inf")


def test_having_eaten_they_can_still_drink_at_a_wine_bar():
    ate = request(no_dinner=True)
    cave = item("cave", "Terra bar à vins", ["gastronomie", "bar", "restaurant"], kind="permanent", hours="Mo-Su 18:00-01:00", venue="Terra")
    rooftop = item("toit", "Le rooftop du Perchoir", ["restaurant"], kind="permanent", hours="Mo-Su 18:00-01:00", venue="Perchoir")
    jazz = item("jazz", "Soirée jazz au Duc", ["concert", "restaurant"], occurrences=[at(21)], venue="Duc des Lombards")
    cruise = item("croisiere", "Dîner-croisière sur la Seine", ["croisiere", "restaurant"], occurrences=[at(20)], venue="Bateau")
    table = item("table", "Bistrot du coin", ["restaurant"], kind="permanent", hours="Mo-Su 12:00-23:00", venue="Bistrot")
    roles = {entry["external_id"]: parcours.role(entry["activity"], parcours.describe(entry["activity"])["tags"], ate=True) for entry in (cave, rooftop, jazz, cruise, table)}
    assert roles == {"cave": "verre", "toit": "verre", "jazz": "sortie", "croisiere": "repas", "table": "repas"}
    kept = {c.key[1]: c for c in _scored_or_none([cave, rooftop, jazz, cruise], ate)}
    assert kept["cave"].role == "verre" and kept["cave"].basis.startswith("Sans réservation") and kept["cave"].score > float("-inf")
    assert kept["jazz"].role == "sortie" and kept["croisiere"].score == float("-inf")
    # Hungry, the same wine bar is a dinner.
    assert parcours.role(cave["activity"], parcours.describe(cave["activity"])["tags"]) == "repas"


def _scored_or_none(entries, req):
    candidates = [parcours.build_candidate(entry, req, None) for entry in entries]
    for candidate in filter(None, candidates):
        candidate.score = parcours.score(candidate, req)
    return filter(None, candidates)


def test_changing_a_step_never_gives_it_back_under_another_listing():
    req, candidates, route = _night()
    # The same immersive show, sold on a second platform.
    twin = item("immersif-bis", "EXPÉRIENCE IMMERSIVE", ["lieu_insolite"], occurrences=[at(20, 15)], lat=48.861, venue="Salle")
    candidates = candidates + _scored([twin], req)
    steps = parcours.replace_step(route, 1, candidates, req, {("test", "immersif")})
    assert [s.candidate.key[1] for s in steps] == ["bar", "autre", "club"]
    # Only the twin left besides the step itself: nothing to offer rather than the same show.
    others = [c for c in candidates if c.key[1] != "autre"]
    assert parcours.replace_step(route, 1, others, req, {("test", "immersif")}) is None


def test_a_play_named_after_a_dinner_is_an_outing_never_the_dinner():
    play = item("piece", "Dîner De Famille", ["theatre"], occurrences=[at(19, 30)], venue="Café de la Gare")
    table = item("table", "Dîner au restaurant", ["restaurant"], occurrences=[at(19, 30)], venue="Resto")
    roles = {c.key[1]: c.role for c in _scored([play, table], request())}
    assert roles == {"piece": "sortie", "table": "repas"}
    # Having eaten, the play is still a play to see.
    play_ate, _ = _scored([play, table], request(no_dinner=True))
    assert play_ate.role == "sortie" and play_ate.score > float("-inf")


def test_an_ordinary_play_comes_after_the_unusual_the_more_so_for_a_daring_couple():
    play = item("piece", "Une comédie de boulevard", ["theatre"], occurrences=[at(20)])
    workshop = item("atelier", "Atelier cocktails", ["atelier"], occurrences=[at(20)])
    def gap(**extra):
        req = request(vibes=["rire"], **extra)
        c = {e["external_id"]: parcours.build_candidate(e, req, None) for e in (play, workshop)}
        for candidate in c.values():
            candidate.vibes = ["rire"]  # both answer the wish; only the kind of outing differs
        return parcours.score(c["atelier"], req) - parcours.score(c["piece"], req)
    assert gap(audace=1.0) > gap(audace=0.0) > 0
    # Stand-up stays a good answer when they asked to laugh.
    club = item("club", "Comedy club", ["humour"], occurrences=[at(20)])
    req = request(vibes=["rire"], audace=1.0)
    candidate = parcours.build_candidate(club, req, None)
    candidate.vibes = ["rire"]
    ordinary = parcours.build_candidate(item("club2", "Comedy club", ["theatre"], occurrences=[at(20)]), req, None)
    ordinary.vibes = ["rire"]
    assert parcours.score(candidate, req) > parcours.score(ordinary, req)


def test_never_a_step_without_photo_or_text():
    fiche = item("f", "Le Festin Nu", ["bar"])
    assert not parcours.shown(fiche)  # no text
    fiche["enrichment"]["description"] = "Grignote d'insectes dans un bar psyché."
    assert parcours.shown(fiche)
    fiche["activity"]["image"] = None
    assert not parcours.shown(fiche)


def test_without_the_photo_filters_a_step_may_have_no_photo(monkeypatch):
    monkeypatch.undo()  # unshown itself, not conftest's
    monkeypatch.setattr(parcours, "IMAGE_FILTERS", False)
    fiche = item("f", "Le Festin Nu", ["bar"])
    fiche["enrichment"]["description"] = "Grignote d'insectes dans un bar psyché."
    fiche["activity"]["image"] = None
    assert parcours.shown(fiche)
    req, candidates, route = _night()
    assert parcours.unshown(route.steps) == set()  # no image asked for


def test_a_redrawn_step_is_close_to_the_one_before():
    req = request(vibes=["insolite"])
    entries = [
        item("bar", "Bar à cocktails", ["bar"], kind="permanent", hours="Mo-Su 18:00-02:00", venue="Bar"),
        item("immersif", "Expérience immersive", ["lieu_insolite"], occurrences=[at(20, 15)], lat=48.861, venue="Salle"),
        item("pres", "Parcours sensoriel dans le noir", ["lieu_insolite"], occurrences=[at(21)], lat=48.8615, venue="Noir"),
        item("loin", "Musée des illusions", ["lieu_insolite"], occurrences=[at(21)], lat=48.878, venue="Loin"),
    ]
    bar, immersif, pres, loin = candidates = _scored(entries, req)
    route = parcours.Route([parcours._step(bar, at(19), req), parcours._step(immersif, at(20, 15), req, 5, 0.2)])
    # The far one scores a little better on its own; the one next to the bar is drawn.
    loin.score = pres.score + 1
    steps = parcours.replace_step(route, 1, candidates, req, {immersif.key})
    assert steps[1].candidate is pres


def test_a_step_taken_out_and_the_next_reached_from_the_one_before(tmp_path, monkeypatch):
    req, candidates, route = _night()
    monkeypatch.setattr(parcours, "DB", tmp_path / "s.db")
    route.request = req
    parcours.save("essai", {"routes": [route], "requests": [req], "seen": set()})
    assert parcours.remove("essai", 0, 1) is None
    bar, club = parcours.load("essai")["routes"][0].steps
    assert (bar.candidate.key[1], club.candidate.key[1]) == ("bar", "club")
    assert club.distance == parcours.distance_km((bar.candidate.lat, bar.candidate.lon), (club.candidate.lat, club.candidate.lon))
    assert parcours.remove("essai", 0, 0) is None
    [club] = parcours.load("essai")["routes"][0].steps
    assert club.travel == 0
    assert parcours.remove("essai", 0, 0) == "une soirée garde au moins une étape"


def test_the_activities_of_a_chosen_evening_are_never_proposed_again(tmp_path, monkeypatch):
    req, candidates, route = _night()
    monkeypatch.setattr(parcours, "DB", tmp_path / "s.db")
    route.request = req
    parcours.save("essai", {"routes": [route], "requests": [req], "seen": set()})
    with open_store(tmp_path / "s.db") as store:
        done = store.chosen_activities(["essai", "absente"])
    assert done == {s.candidate.key for s in route.steps}
    base = parcours.Base([c.item for c in candidates], {c.key: 35 for c in candidates})
    req.done = done
    with open_store(tmp_path / "s.db") as store:
        left = parcours.candidates_for(store, base, req, checks=0)
    assert left and not {c.key for c in left} & done


def test_a_route_drawn_again_has_its_steps_back_after_some_were_taken_out(tmp_path, monkeypatch):
    req, candidates, route = _night()
    monkeypatch.setattr(parcours, "DB", tmp_path / "s.db")
    monkeypatch.setattr(parcours, "candidates_for", lambda store, base, request, checks: candidates)
    route.request = req
    parcours.save("essai", {"routes": [route], "requests": [req], "seen": set()})
    assert parcours.remove("essai", 0, 1) is None
    # The best draw has two steps; the route was composed with three.
    short, full = parcours.Route(route.steps[:2], 10.0), parcours.Route(route.steps, 1.0)
    monkeypatch.setattr(parcours, "compose", lambda found, request: [short, full])
    base = parcours.Base([c.item for c in candidates], {c.key: 35 for c in candidates})
    assert parcours.regenerate(None, base, "essai", 0, claude=False) is None
    assert len(parcours.load("essai")["routes"][0].steps) == 3


def test_never_a_route_whose_image_does_not_show(monkeypatch):
    req, candidates, route = _night()
    routes = sorted(parcours.compose(candidates, req), key=lambda r: -r.score)
    dead = parcours.pick(routes, 1)[0].steps[1].candidate.key
    # The best route's show has a dead image: a route without it instead.
    monkeypatch.setattr(parcours, "unshown", lambda steps: {s.candidate.key for s in steps} & {dead})
    [shown] = parcours.pick_shown(routes, 1)
    assert dead not in {s.candidate.key for s in shown.steps}


def test_a_dead_image_is_replaced_by_the_official_sites_before_leaving_the_step_out(tmp_path, monkeypatch):
    monkeypatch.undo()  # the real check (conftest leaves images out of the other tests)
    monkeypatch.setattr(parcours, "IMAGE_FILTERS", True)
    monkeypatch.setattr(parcours, "DB", tmp_path / "s.db")
    monkeypatch.setattr(parcours, "_IMAGES", {})
    req, candidates, route = _night()
    bar, show, club = route.steps
    alive = {"https://example.org/bar.jpg", "https://example.org/club.jpg", "https://site.example/new.jpg"}
    monkeypatch.setattr(parcours.images, "loads", lambda client, url: url in alive)
    monkeypatch.setattr(parcours.images, "replacement", lambda client, item, url: "https://site.example/new.jpg" if item is bar.candidate.item else None)
    bar.candidate.item["activity"]["image"]["url"] = "https://example.org/dead-bar.jpg"
    # The bar gets its site's image; the show, with nothing else, is left out and recorded dead.
    assert parcours.unshown(route.steps) == {show.candidate.key}
    assert parcours.images.of(bar.candidate.item) == "https://site.example/new.jpg"
    with open_store(tmp_path / "s.db") as store:
        assert store.page_checks()["https://example.org/immersif.jpg"] == ("image", True, None)


def test_secret_title_names_the_quarter_never_the_venue():
    _, _, route = _night()
    assert parcours.secret_title(route) == "Les Noctambules de Beaubourg"  # a night out, at the heart of Beaubourg
    assert parcours.route_json(0, route)["secret_title"] == parcours.secret_title(route)
    # A quarter named like a venue of the evening would give it away: the next one names it.
    route.steps[0].candidate.venue = "Centre Pompidou, Beaubourg"
    assert parcours.secret_title(route) == "Les Noctambules des Halles"
    for step in route.steps:
        step.candidate.lat, step.candidate.lon = 48.80, 2.20
        step.candidate.item["activity"]["venue"]["town"] = "Issy-les-Moulineaux"
    assert parcours.secret_title(route).endswith(" d'Issy-les-Moulineaux")


def test_concerts_keep_to_the_couple_music():
    req = request(vibes=["musique"], genres={"jazz"})
    techno = item("techno", "Concert techno", ["concert"], occurrences=[at(21)])
    jazz = item("jazz", "Jazz au caveau", ["concert"], occurrences=[at(21)])
    candlelight = item("bougies", "Candlelight : Vivaldi", ["concert"], occurrences=[at(21)])
    unknown = item("inconnu", "Mica Millar", ["concert"], occurrences=[at(21)])
    scores = {c.key[1]: c.score for c in _scored([techno, jazz, candlelight, unknown], req)}
    assert scores["techno"] == float("-inf")
    assert min(scores["jazz"], scores["bougies"], scores["inconnu"]) > float("-inf")
    assert scores["jazz"] > scores["inconnu"]  # their music comes first


def test_the_couples_votes_favour_a_kind_and_leave_out_one_voted_down_twice():
    entries = [
        item("pirates", "Escape game des pirates", ["jeux"], occurrences=[at(20)]),
        item("louvre", "Escape game du Louvre", ["jeux"], occurrences=[at(20)]),  # an escape game, and art
        item("quiz", "Quiz au pub", ["jeux"], occurrences=[at(20)]),
        item("blind", "Blind test du jeudi", ["jeux"], occurrences=[at(20)]),
        item("annees80", "Blind test des années 80", ["jeux"], occurrences=[at(20)]),
    ]
    base = parcours.Base(entries, {(e["source_id"], e["external_id"]): 35 for e in entries})

    def scores(votes):
        req = request(vibes=["defi"], tastes=parcours.tastes_from(base, {("test", key): vote for key, vote in votes.items()}))
        return {c.key[1]: parcours.score(c, req) for c in (parcours.build_candidate(e, req, None) for e in entries)}

    plain = scores({})
    assert parcours.tastes_from(base, {("test", "louvre"): 1}) == {"escape_game": 1, "art": 1}
    # An escape game liked: the other one comes first, the quizzes do not move.
    liked = scores({"pirates": 1})
    assert liked["louvre"] == pytest.approx(plain["louvre"] + parcours.TASTE_UP)
    assert liked["quiz"] == plain["quiz"]
    # Liked again and again: no more than TASTE_MAX.
    many = parcours.taste({"escape_game"}, request(tastes={"escape_game": 9}))
    assert many == parcours.TASTE_MAX
    # A quiz voted down: the others weigh less, a "no" more than a "yes"; liked and not liked, it is even.
    once = scores({"quiz": -1})
    assert once["blind"] == pytest.approx(plain["blind"] - parcours.TASTE_DOWN)
    assert parcours.tastes_from(base, {("test", "quiz"): -1, ("test", "blind"): 1}) == {}
    # Two voted down: no quiz at all any more, the escape games still.
    out = scores({"quiz": -1, "blind": -1})
    assert out["annees80"] == float("-inf") and out["pirates"] == plain["pirates"]
    # Before any check, the engines are asked for a kind voted out last, not never.
    req = request(vibes=["defi"], tastes={"quiz": -2})
    assert parcours.quick_score(entries[4], req) == pytest.approx(parcours.quick_score(entries[4], request(vibes=["defi"])) - parcours.TASTE_MIN)
    # An activity that left the base since is not counted.
    assert parcours.tastes_from(base, {("test", "absente"): -1}) == {}


def test_the_tastes_are_kept_with_the_evening_for_its_redraws():
    req = request(tastes={"quiz": -2.0, "escape_game": 1.0})
    assert parcours._decode(json.loads(parcours._json([req])))[0].tastes == {"quiz": -2.0, "escape_game": 1.0}
    # An evening saved before the votes: none.
    data = parcours._encode(request())
    del data["tastes"]
    assert parcours._decode(data).tastes == {}


# Secret Squad: an evening for a band of friends ------------------------------------------------------------------


def squad(party=6, **extra):
    return request(**{"party": party, "formule": "squad", "budget": 60 * party, "vibes": ["rire", "fete"], **extra})


def test_a_band_pays_for_each_of_them():
    def offer(unit, price=20):
        return {"offers": [{"is_free": False, "price_min": price, "price_unit": unit}]}

    assert parcours.price_for(offer("per_person"), "sortie", 6) == (120, False)
    assert parcours.price_for(offer("per_couple", 50), "sortie", 5) == (150, False)  # three couples' tickets for five
    assert parcours.price_for(offer("per_group", 180), "sortie", 6) == (180, False)
    assert parcours.price_for({"offers": []}, "verre", 6) == (90, True)  # the estimate for two, by head
    assert parcours.price_for(offer("per_person"), "sortie") == (40, False)  # a couple, as before
    show = item("show", "Stand-up", ["humour"], occurrences=[at(20)])
    assert parcours.build_candidate(show, squad(), None).price == 120


def test_each_offer_is_for_its_party():
    hen = item("evjf", "Atelier cocktails EVJF", ["atelier"], occurrences=[at(20)])
    massage = item("duo", "Massage en duo", ["bien_etre"], occurrences=[at(20)])
    room = item("room", "Escape game : Prison Break", ["jeux"], occurrences=[at(20)])
    room["activity"] |= {"players_min": 4, "players_max": 6}
    # A hen party is a band's, a massage for two a couple's.
    assert parcours.build_candidate(hen, request(), None) is None and parcours.build_candidate(hen, squad(), None)
    assert parcours.build_candidate(massage, request(), None) and parcours.build_candidate(massage, squad(), None) is None
    # An escape room for 4 to 6: neither two nor eight.
    assert parcours.build_candidate(room, request(), None) is None
    assert parcours.build_candidate(room, squad(6), None) and parcours.build_candidate(room, squad(8), None) is None
    # Not even a live check spent on one not for the party.
    assert parcours.quick_score(room, request()) == float("-inf") and parcours.quick_score(room, squad()) > 0
    # Two friends are a band, not a couple: no massage for two, the hen party's workshop if they like.
    assert parcours.build_candidate(massage, squad(2), None) is None and parcours.build_candidate(hen, squad(2), None)
    assert parcours.build_candidate(room, squad(2), None) is None


def test_a_band_likes_what_a_group_shares_where_a_couple_likes_romance():
    karaoke = item("karaoke", "Karaoké en cabine privée", ["bar"], occurrences=[at(21)])
    candles = item("bougies", "Candlelight : Vivaldi aux chandelles", ["concert"], occurrences=[at(21)])

    def scores(req):
        return {c.key[1]: c.score for c in _scored([karaoke, candles], req)}

    couple = scores(request(vibes=["fete", "musique"]))
    band = scores(squad(vibes=["fete", "musique"]))
    assert couple["bougies"] > couple["karaoke"] and band["karaoke"] > band["bougies"]


def test_a_big_band_would_rather_book_than_stand_at_the_door():
    bar = item("bar", "Bar à cocktails", ["bar"], kind="permanent", hours="Mo-Su 18:00-02:00")
    small, big = squad(4), squad(parcours.WALK_IN_PARTY + 2)
    walk_in = lambda req: parcours.score(parcours.build_candidate(bar, req, None), req)  # noqa: E731
    assert walk_in(big) < walk_in(small)


def test_a_bands_evening_is_named_and_told_as_theirs():
    req, _, route = _night()
    band = squad(6, vibes=["insolite", "fete"])
    assert parcours.secret_title(route, squad=True) == "La Virée de Beaubourg"  # a night out, the band's words
    shown = parcours.route_json(0, route, band)
    assert (shown["secret_title"], shown["formule"], shown["personnes"]) == ("La Virée de Beaubourg", "squad", 6)
    parcours.name_by_rules(route, band)
    assert f"pour environ {route.price / 6:.0f} € par personne" in route.pitch and "à deux" not in route.pitch
    # Kept with the evening, for its redraws; an evening saved before the formulas is a couple's.
    assert parcours._decode(json.loads(parcours._json([band])))[0].formule == "squad"
    data = parcours._encode(request())
    del data["formule"]
    assert parcours._decode(data).formule == "duo" and not parcours._decode(data).squad
