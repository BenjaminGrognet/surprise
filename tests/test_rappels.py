"""The reminders that belong to no evening (surprise.rappels) and the weather of an evening's steps out in the open
(surprise.meteo, surprise.courriers): who is told what and when, each once; a date's three intrigues composed before
its email goes, its button opening them; and a whole pass on the local Supabase (npm run db:start), never the
project's. The relay, the composition and Open-Meteo are stand-ins: nothing leaves the machine."""

import uuid
from dataclasses import replace
from datetime import date, datetime, time, timedelta

import psycopg
import pytest

from surprise import courriers, mail, meteo, parcours, rappels
from surprise.courriers import Person
from surprise.rappels import Duo, KeyDate
from test_courriers import kept, links, relay, route, paris  # noqa: F401 (the fixtures)
from test_push import local_db  # noqa: F401 (the fixture)

PARIS = parcours.PARIS
LEA, SAM = Person("lea@example.com", "u-lea"), Person("sam@example.com", "u-sam")


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), PARIS)


@pytest.fixture(autouse=True)
def no_forecast(monkeypatch):
    """Open-Meteo is never asked from the tests: no rain anywhere unless a test says otherwise."""
    monkeypatch.setattr(meteo, "cached", lambda lat, lon, day: None)
    monkeypatch.setattr(meteo, "fetch", lambda *args, **kwargs: None)


def due_keys(reminders, now):
    return sorted((r.moment.key, r.moment.to.address) for r in reminders if courriers.due(r.moment, now))


def test_a_date_that_counts_three_weeks_before_to_both_but_a_birthday_only_to_the_other():
    met = KeyDate("d1", "Notre rencontre", "rencontre", 3, 20)
    birthday = KeyDate("d2", "L'anniversaire de Sam", "anniversaire", 3, 25, birthday_of="u-sam")
    duo = Duo("duo1", [LEA, SAM], [met, birthday])
    today = date(2027, 2, 20)
    reminders = rappels.date_reminders(duo, today)
    # Three weeks before at ten, until two weeks before: the meeting to both, Sam's birthday to Léa alone.
    assert due_keys(reminders, at(date(2027, 2, 27), 9, 59)) == []
    assert due_keys(reminders, at(date(2027, 2, 27), 10)) == [("date:d1:2027-03-20", LEA.address), ("date:d1:2027-03-20", SAM.address)]
    assert due_keys(reminders, at(date(2027, 3, 4), 12)) == [("date:d1:2027-03-20", LEA.address), ("date:d1:2027-03-20", SAM.address),
                                                              ("date:d2:2027-03-25", LEA.address)]
    assert due_keys(reminders, at(date(2027, 3, 9), 12)) == [("date:d2:2027-03-25", LEA.address)]
    meeting = next(r for r in reminders if r.moment.key == "date:d1:2027-03-20")
    assert meeting.compose == ("rencontre", date(2027, 3, 20))
    assert meeting.moment.subject == "« Notre rencontre » approche : trois intrigues vous attendent"
    assert meeting.moment.lines[0].startswith("Samedi 20 mars, c'est « Notre rencontre ».")


def test_saint_valentin_for_every_duo_of_two_and_the_next_year_once_passed():
    reminders = rappels.date_reminders(Duo("duo1", [LEA, SAM]), date(2027, 1, 20))
    assert due_keys(reminders, at(date(2027, 1, 24), 10)) == [("date:saint-valentin:2027-02-14", LEA.address), ("date:saint-valentin:2027-02-14", SAM.address)]
    assert next(r for r in reminders).moment.subject == "La saint-valentin approche : trois intrigues vous attendent"
    assert rappels.date_reminders(Duo("duo1", [LEA]), date(2027, 1, 20)) == []  # a duo waiting for its second
    later = rappels.date_reminders(Duo("duo1", [LEA, SAM]), date(2027, 2, 15))
    assert {r.moment.key for r in later} == {"date:saint-valentin:2028-02-14"}
    assert rappels.next_day(2, 29, date(2027, 1, 1)) == date(2027, 2, 28)


def test_a_season_ten_days_before_to_the_accounts_without_an_evening_that_day():
    halloween = {"id": "halloween", "nom": "Halloween", "texte": "Le soir des frissons.", "deroule": "Un verre étrange, puis des frissons.",
                 "envies": ["frissons"], "debut": date(2026, 10, 31), "fin": date(2026, 10, 31)}
    busy = {"u-sam": {date(2026, 10, 31)}}
    reminders = rappels.season_reminders([LEA, SAM], [halloween], busy, date(2026, 10, 15))
    assert due_keys(reminders, at(date(2026, 10, 21), 9)) == []
    assert due_keys(reminders, at(date(2026, 10, 21), 10)) == [("saison:halloween:2026", LEA.address)]
    assert due_keys(reminders, at(date(2026, 10, 28), 21)) == []  # three days before: too late to suggest
    moment = reminders[0].moment
    assert moment.subject == "Halloween, samedi 31 octobre"
    assert moment.button == ("Composer une soirée de saison", "/soiree?formule=duo&envies=frissons&jour=2026-10-31")
    assert moment.lines[1] == "Notre idée : un verre étrange, puis des frissons."


def test_a_year_since_an_evening_on_its_day_to_its_two_on_the_same_wishes():
    evening = {"id": "s1", "secret_title": "Le Pacte du Marais", "day": date(2025, 10, 17), "envies": ["rire", "jouer"], "people": [LEA, SAM]}
    reminders = rappels.anniversary_reminders([evening], date(2026, 10, 17))
    assert due_keys(reminders, at(date(2026, 10, 17), 10)) == [("un-an:s1", LEA.address), ("un-an:s1", SAM.address)]
    assert due_keys(reminders, at(date(2026, 10, 17), 21)) == []
    assert reminders[0].moment.button == ("On remet ça ?", "/soiree?formule=duo&envies=rire%2Cjouer")


def test_rain_is_read_at_each_outdoor_steps_hour_once_per_place_and_day():
    asked = []

    def forecast(lat, lon, day):
        asked.append((lat, lon, day))
        return {"hourly": {"time": [f"{day}T{h:02d}:00" for h in range(24)], "precipitation_probability": [10] * 20 + [75, 80, 20, 0]}}

    route = {"steps": [
        {"title": "Guinguette", "outdoor": True, "lat": 48.86, "lon": 2.35, "start": "2026-10-16T20:30:00+02:00"},
        {"title": "Balade", "outdoor": True, "lat": 48.861, "lon": 2.351, "start": "2026-10-16T22:15:00+02:00"},
        {"title": "Cabaret", "outdoor": False, "lat": 48.87, "lon": 2.33, "start": "2026-10-16T21:00:00+02:00"},
    ]}
    rainy = meteo.rainy_steps(route, forecast)
    assert [(step["title"], chance) for step, chance in rainy] == [("Guinguette", 75)]  # 22h: 20 %, the cabaret is covered
    assert asked == [(48.86, 2.35, "2026-10-16")]  # the two outdoor steps share their forecast
    assert meteo.rain_chance(None, datetime(2026, 10, 16, 20)) is None
    assert meteo.rainy_steps(route, lambda *a: None) == []


def test_rain_two_days_before_tells_the_instigateur_once_and_offers_the_plan_b(kept, local_db, relay, monkeypatch):
    rainy_route = []

    def forecast(lat, lon, day):
        rainy_route.append(day)
        return {"hourly": {"time": [f"{day}T{h:02d}:00" for h in range(24)], "precipitation_probability": [90] * 24}}

    monkeypatch.setattr(meteo, "cached", forecast)
    # Its first step out in the open, as a terrace would be.
    monkeypatch.setattr(parcours, "step_json", _outdoor(parcours.step_json))
    via = mail.relay("smtp://relay.example.com")
    a = kept["addresses"]
    assert all(m.key != "meteo" for m, _ in courriers.run(local_db, paris(-3, 12), via=via, dry_run=True).sent)  # three days before: not yet
    report = courriers.run(local_db, paris(-2, 10, 30), via=via)
    told = [(m.key, m.to.address) for m, channel in report.sent if channel == "email" and m.key == "meteo"]
    assert told == [("meteo", a["lea"])]
    letter = next(m for m in relay.last.messages if m["Subject"].startswith("Pluie annoncée"))
    assert letter["Subject"] == "Pluie annoncée pour « Le Pacte du Marais »"
    assert "90 % de risque de pluie" in letter.get_body(("plain",)).get_content()
    assert "/revelation?soiree=" in letter.get_body(("plain",)).get_content()
    # Once told, the forecast is not read again for it.
    rainy_route.clear()
    assert all(m.key != "meteo" for m, _ in courriers.run(local_db, paris(-2, 11), via=via).sent)
    assert rainy_route == []


def _outdoor(original):
    def step_json(step, redo, page=None):
        found = original(step, redo, page)
        return found | {"outdoor": bool(redo) and redo.endswith("steps/0")}
    return step_json


@pytest.fixture
def duo(local_db):
    """Léa and Sam in a duo of the local Supabase, the day they met noted; Léa with her web browser allowed."""
    tag = uuid.uuid4().hex[:8]
    addresses = {name: f"{name}-{tag}@example.com" for name in ("lea", "sam")}
    with psycopg.connect(local_db, autocommit=True) as conn:
        ids = {name: conn.execute(
            "insert into auth.users (id, email, aud, role) values (gen_random_uuid(), %s, 'authenticated', 'authenticated') returning id::text",
            (address,),
        ).fetchone()[0] for name, address in addresses.items()}
        duo_id = conn.execute("insert into public.duos default values returning id::text").fetchone()[0]
        for name in ("lea", "sam"):
            conn.execute("insert into public.duo_members (user_id, duo_id, email) values (%s, %s, %s)", (ids[name], duo_id, addresses[name]))
        conn.execute("insert into public.dates_cles (duo_id, author, label, genre, mois, jour) values (%s, %s, 'Notre rencontre', 'rencontre', 11, 20)",
                     (duo_id, ids["lea"]))
    yield {"ids": ids, "addresses": addresses, "duo": duo_id}
    with psycopg.connect(local_db, autocommit=True) as conn:
        conn.execute("delete from auth.users where id::text = any(%s)", (list(ids.values()),))
        conn.execute("delete from public.duos where id::text = %s", (duo_id,))


def test_a_pass_composes_a_dates_intrigues_once_emails_them_and_keeps_them_for_the_app(duo, local_db, relay):
    composed = []

    # The local base may hold other duos (the app's tests): only this one's counted.
    ours = set(duo["addresses"].values())

    def compose(user_id, genre, day):
        if user_id in duo["ids"].values():
            composed.append((user_id, genre, day))
        return f"page-{user_id[:8]}"

    via = mail.relay("smtp://relay.example.com")
    now = at(date(2026, 10, 30), 10, 30)  # three weeks before 20 November
    simulated = rappels.run(local_db, now, via=via, dry_run=True, compose=compose)
    mine = sorted((m.key, m.to.address) for m, channel in simulated.sent if channel.startswith("email") and m.key.startswith("date:") and m.to.address in ours)
    assert mine == sorted([("date:" + _key(local_db, duo) + ":2026-11-20", a) for a in duo["addresses"].values()])
    assert composed == []  # a dry run composes nothing

    report = rappels.run(local_db, now, via=via, compose=compose)
    emailed = {m.to.address: m for m, channel in report.sent if channel == "email" and m.key.startswith("date:") and m.to.address in ours}
    assert set(emailed) == set(duo["addresses"].values())
    assert sorted(composed) == sorted((duo["ids"][n], "rencontre", date(2026, 11, 20)) for n in ("lea", "sam"))
    lea = emailed[duo["addresses"]["lea"]]
    assert lea.button == ("Voir les trois intrigues", f"/soiree?soiree=page-{duo['ids']['lea'][:8]}")
    with psycopg.connect(local_db) as conn:
        ready = conn.execute("select page_name, day, label from public.intrigues_pretes where user_id = %s", (duo["ids"]["lea"],)).fetchall()
    assert ready == [(f"page-{duo['ids']['lea'][:8]}", date(2026, 11, 20), "« Notre rencontre »")]
    # Noted: nothing again, nothing composed again.
    composed.clear()
    assert [m for m, _ in rappels.run(local_db, now + timedelta(minutes=10), via=via, compose=compose).sent if m.key.startswith("date:") and m.to.address in ours] == []
    assert composed == []


def _key(db, duo):
    with psycopg.connect(db) as conn:
        return conn.execute("select id::text from public.dates_cles where duo_id::text = %s", (duo["duo"],)).fetchone()[0]


def test_a_dates_intrigues_are_composed_with_the_couples_profile_its_evenings_and_tastes(duo, local_db, monkeypatch):
    from surprise import quiz

    asked = {}
    monkeypatch.setattr(parcours.Base, "load", classmethod(lambda cls, store: "la base"))

    def compose(store, found, profile, envies, **settings):
        asked.update(found=found, profile=profile, envies=envies, **settings)
        return "soiree-prete"

    monkeypatch.setattr(quiz, "compose", compose)
    profile = quiz.profile_from({"audace": "classique"})
    with psycopg.connect(local_db, autocommit=True) as conn:
        # Sam made the couple's profile; Léa kept an evening and voted one step down.
        conn.execute("insert into public.couple_profiles (id, user_id, answers, profile) values (%s, %s, '{}', %s)",
                     (f"p-{duo['ids']['sam']}", duo["ids"]["sam"], psycopg.types.json.Jsonb(profile)))
        conn.execute("insert into public.soirees_choisies (user_id, page_name, title, pitch, day) values (%s, 'soiree-passee', 'T', 'P', '2026-09-01')",
                     (duo["ids"]["lea"],))
        conn.execute("insert into public.gouts (user_id, activity_id, vote) values (%s, 'fever:42', -1)", (duo["ids"]["lea"],))
    page = rappels.compose_for(local_db)(duo["ids"]["lea"], "anniversaire", date(2026, 11, 20))
    assert page == "soiree-prete"
    assert asked["found"] == "la base" and asked["profile"]["audace"] == profile["audace"]  # the partner's profile
    assert (asked["envies"], asked["occasion"], asked["days"], asked["dinner"]) == (["romantique"], "anniversaire", [date(2026, 11, 20)], True)
    assert asked["chosen"] == ["soiree-passee"] and asked["votes"] == {("fever", "42"): -1} and asked["checks"] == 0


def test_a_duo_without_its_profile_told_the_day_after_it_formed_then_four_days_later_never_once_made():
    duo = Duo("duo1", [LEA, SAM], formed=date(2027, 3, 1), profiled=False)
    reminders = rappels.profile_reminders(duo, date(2027, 3, 1))
    assert due_keys(reminders, at(date(2027, 3, 1), 12)) == []
    assert due_keys(reminders, at(date(2027, 3, 2), 10)) == [("profil:duo1:1", LEA.address), ("profil:duo1:1", SAM.address)]
    assert due_keys(reminders, at(date(2027, 3, 5), 12)) == []  # three days, then quiet
    assert due_keys(reminders, at(date(2027, 3, 6), 10)) == [("profil:duo1:2", LEA.address), ("profil:duo1:2", SAM.address)]
    first = reminders[0].moment
    assert first.subject == "Votre profil de couple, en deux minutes" and first.button == ("Faire notre profil", "/profil")
    assert "questions du jour" in first.lines[1]
    assert rappels.profile_reminders(replace(duo, profiled=True), date(2027, 3, 2)) == []


def test_a_pass_tells_a_duo_without_profile_and_no_more_once_one_of_them_made_it(duo, local_db):
    ours = set(duo["addresses"].values())
    tomorrow = datetime.now(PARIS).date() + timedelta(days=1)
    told = lambda: sorted(m.to.address for m, channel in rappels.run(local_db, at(tomorrow, 10, 30), via=mail.relay("smtp://relay.example.com"), dry_run=True).sent  # noqa: E731
                          if channel.startswith("email") and m.key == f"profil:{duo['duo']}:1" and m.to.address in ours)
    assert told() == sorted(ours)
    with psycopg.connect(local_db, autocommit=True) as conn:
        conn.execute("insert into public.couple_profiles (id, user_id, answers, profile) values (%s, %s, '{}', '{}')", (duo["ids"]["sam"], duo["ids"]["sam"]))
    assert told() == []
