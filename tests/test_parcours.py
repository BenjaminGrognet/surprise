from datetime import date, datetime, timedelta

from surprise import parcours
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


def test_page_has_a_booking_link_under_each_step():
    req = request()
    candidates = [
        parcours.build_candidate(item("a", "Comedy club", ["humour"], occurrences=[at(19, 30)], venue="Club"), req, None),
        parcours.build_candidate(item("b", "Concert aux chandelles", ["concert"], occurrences=[at(21, 30)], venue="Église"), req, None),
    ]
    route = parcours.Route([parcours.Step(candidates[0], at(19, 30), at(21)), parcours.Step(candidates[1], at(21, 30), at(23), travel=5, distance=0.3)])
    parcours.name_by_rules(route, req)
    page = parcours.render([route], req)
    assert page.count(">Réserver</a>") == 2 and "https://www.billetweb.fr/a" in page
    assert "Séance de 21:30" in page and "travelmode=walking" in page


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
    # The only other evening would repeat a step: the whole route has no other draw.
    assert parcours.regenerate(None, None, "essai", 0, claude=False) == "aucun autre parcours complet ce soir-là"
    assert parcours.regenerate(None, None, "absent", 0, claude=False) == "parcours introuvable : relancez la composition"


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
