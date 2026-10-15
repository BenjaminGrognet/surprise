"""The reminders that belong to no evening (docs/complicite.md, phase 3), by email and pushed to the web as the
evenings' own (surprise.courriers), from the accounts in Supabase (SUPABASE_DB_URL):

- the dates that count for a duo (public.dates_cles: when they met, each one's birthday) and Saint-Valentin for every
  duo: three weeks before, three intrigues composed for that day (quiz.compose, the couple's profile and tastes),
  ready in the app (public.intrigues_pretes); a birthday reminds only the other one;
- the seasons of Paris (public.saisons_a_venir): ten days before, to the accounts that compose evenings for two and
  have none that day;
- a year since an evening for two: its day, to its instigateur and its passager;
- a duo without its profile (surprise.quiz), neither of its two having made it: the day after it formed, then four days
  later, to both, the profile being where a couple starts (its evenings and its questions du jour follow it).

Each goes once per account and channel (pipeline.rappels), between 9:00 and 21:00, while it still makes sense; never to
an account that stopped them, nor to an address stopped from an email's link.

    uv run --env-file .env python -m surprise.rappels --dry-run    # what would go now, nothing sent nor composed
"""

import argparse
import os
import sys
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from typing import Any, Callable
from urllib.parse import quote, urlencode

import psycopg

from surprise import courriers, mail, parcours, push
from surprise.courriers import Moment, Person, long_day

PARIS = parcours.PARIS
# Three weeks before a date, until two weeks before: time to book.
DATE_AHEAD, DATE_UNTIL = 21, 14
# A duo without its profile told the day after it formed, then four days later, each time for three days.
PROFILE_AFTER = (1, 5)
PROFILE_FOR = 3
# Ten days before a season, until three days before.
SEASON_AHEAD, SEASON_UNTIL = 10, 3
VALENTINE = (2, 14)
# What an evening for each kind of date wishes for (surprise.quiz.ENVIES, OCCASIONS).
DATE_WISHES = {
    "rencontre": (["romantique", "nous"], "retrouvailles"),
    "anniversaire": (["romantique"], "anniversaire"),
    "saint-valentin": (["romantique"], "grande"),
    "autre": (["nous"], "rien"),
}


@dataclass(frozen=True)
class KeyDate:
    """A date that counts for a duo: its key, its words, its kind, and when it comes back."""

    key: str  # the date's id, or saint-valentin
    label: str
    genre: str
    month: int
    day: int
    birthday_of: str | None = None  # the account whose birthday it is: only the other is reminded


@dataclass
class Duo:
    id: str
    members: list[Person]
    dates: list[KeyDate] = field(default_factory=list)
    formed: date | None = None  # its day, in Paris
    profiled: bool = True  # one of its two made the couple's profile


@dataclass(frozen=True)
class Reminder:
    """A moment for an account, with, for a date, the evening to compose before it goes."""

    moment: Moment
    compose: tuple[str, date] | None = None  # (genre, day): three intrigues to compose for that day


def _local(day: date, offset: int, at: time) -> datetime:
    return datetime.combine(day + timedelta(days=offset), at, PARIS)


def next_day(month: int, day: int, today: date) -> date:
    """The next time a day of the year comes, today included (29 February: the 28th in other years)."""
    for year in (today.year, today.year + 1):
        try:
            found = date(year, month, day)
        except ValueError:
            found = date(year, month, 28)
        if found >= today:
            return found
    raise ValueError("unreachable")


def date_reminders(duo: Duo, today: date) -> list[Reminder]:
    """Each date of the duo (and Saint-Valentin) three weeks ahead: to each of the two but the one it celebrates."""
    if len(duo.members) < 2:
        return []
    found = []
    for key_date in [*duo.dates, KeyDate("saint-valentin", "la Saint-Valentin", "saint-valentin", *VALENTINE)]:
        day = next_day(key_date.month, key_date.day, today)
        at, until = _local(day, -DATE_AHEAD, time(10)), _local(day, -DATE_UNTIL, time(21))
        for person in duo.members:
            if person.user_id == key_date.birthday_of:
                continue
            words = key_date.label if key_date.genre == "saint-valentin" else f"« {key_date.label} »"
            found.append(Reminder(Moment(
                f"date:{key_date.key}:{day.isoformat()}", person, at, until,
                f"{words.capitalize() if words[0].islower() else words} approche : trois intrigues vous attendent",
                (f"{long_day(day).capitalize()}, c'est {words}. Nous avons composé trois soirées pour ce jour-là, à votre image.",
                 "Gardez celle qui vous ressemble : il reste trois semaines pour réserver, et le secret reste entier."),
                ("Voir les trois intrigues", "/soiree"),
                f"{long_day(day).capitalize()}, c'est {words} : trois intrigues vous attendent.",
            ), compose=(key_date.genre, day)))
    return found


def profile_reminders(duo: Duo, today: date) -> list[Reminder]:
    """A duo neither of whose two made the couple's profile: to both, twice, the way to it."""
    if duo.profiled or not duo.formed:
        return []
    found = []
    for n, after in enumerate(PROFILE_AFTER, 1):
        at, until = _local(duo.formed, after, time(10)), _local(duo.formed, after + PROFILE_FOR - 1, time(21))
        first = n == 1
        for person in duo.members:
            found.append(Reminder(Moment(
                f"profil:{duo.id}:{n}", person, at, until,
                "Votre profil de couple, en deux minutes" if first else "Il manque votre profil de couple",
                ("Dix questions, une seule fois pour vous deux : où en est votre histoire, jusqu'où vous osez, ce que vous "
                 "ne voulez jamais." if first else "Vos premières intrigues n'attendent plus que lui : sans profil, nous composons à l'aveugle.",
                 "Vos soirées seront composées à votre image, et vos questions du jour suivront ce que vous aimez."),
                ("Faire notre profil", "/profil"),
                "Deux minutes pour votre profil de couple : vos soirées et vos questions du jour à votre image.",
            )))
    return found


def season_reminders(people: list[Person], seasons: list[dict[str, Any]], busy: dict[str, set[date]], today: date) -> list[Reminder]:
    """Each season ten days ahead, to the accounts without an evening on its first day."""
    found = []
    for season in seasons:
        start: date = season["debut"]
        at, until = _local(start, -SEASON_AHEAD, time(10)), _local(start, -SEASON_UNTIL, time(21))
        query = urlencode({"formule": "duo", "envies": ",".join(season["envies"]), "jour": start.isoformat()})
        for person in people:
            if start in busy.get(person.user_id or "", set()):
                continue
            found.append(Reminder(Moment(
                f"saison:{season['id']}:{start.year}", person, at, until, f"{season['nom']}, {long_day(start)}",
                (season["texte"], f"Notre idée : {season['deroule'][0].lower()}{season['deroule'][1:]}"),
                ("Composer une soirée de saison", f"/soiree?{query}"),
                f"{season['nom']}, {long_day(start)} : une soirée de saison ?",
            )))
    return found


def anniversary_reminders(evenings: list[dict[str, Any]], today: date) -> list[Reminder]:
    """An evening for two lived a year ago today: to its instigateur and its passager, « On remet ça ? »."""
    found = []
    for evening in evenings:
        lived: date = evening["day"]
        try:
            again = lived.replace(year=lived.year + 1)
        except ValueError:  # 29 February
            again = date(lived.year + 1, 2, 28)
        query = urlencode({"formule": "duo", "envies": ",".join(evening["envies"] or [])})
        for person in evening["people"]:
            found.append(Reminder(Moment(
                f"un-an:{evening['id']}", person, _local(again, 0, time(10)), _local(again, 0, time(21)),
                f"Il y a un an : « {evening['secret_title']} »",
                (f"Il y a un an jour pour jour, vous viviez « {evening['secret_title']} ». Votre Livre des Secrets s'en souvient.",
                 "On remet ça ? Une nouvelle intrigue sur les mêmes envies, jamais les mêmes lieux."),
                ("On remet ça ?", f"/soiree?{query}"),
                f"Il y a un an : « {evening['secret_title']} ». On remet ça ?",
            )))
    return found


# From Supabase ---------------------------------------------------------------------------------------------------


def _person(row: dict[str, Any]) -> Person:
    return Person(row["email"], row["user_id"], row["emails"])


def duos(conn: psycopg.Connection) -> list[Duo]:
    rows = conn.execute(
        """select d.id::text, (d.created_at at time zone 'Europe/Paris')::date,
                  exists (select 1 from public.couple_profiles c join public.duo_members x on x.user_id = c.user_id where x.duo_id = d.id),
                  json_agg(json_build_object('user_id', m.user_id::text, 'email', u.email, 'emails', coalesce(p.emails, true))),
                  coalesce((select json_agg(json_build_object('id', k.id::text, 'label', k.label, 'genre', k.genre, 'mois', k.mois,
                                                             'jour', k.jour, 'pour', k.pour::text))
                            from public.dates_cles k where k.duo_id = d.id), '[]')
           from public.duos d
           join public.duo_members m on m.duo_id = d.id
           join auth.users u on u.id = m.user_id
           left join public.email_prefs p on p.user_id = m.user_id
           group by d.id, d.created_at"""
    ).fetchall()
    return [Duo(id_, [_person(m) for m in members if m["email"]],
                [KeyDate(k["id"], k["label"], k["genre"], k["mois"], k["jour"], k["pour"]) for k in dates], formed, profiled)
            for id_, formed, profiled, members, dates in rows]


def composers(conn: psycopg.Connection) -> list[Person]:
    """The accounts that compose evenings for two: in a duo of two, or having kept one."""
    rows = conn.execute(
        """select u.id::text, u.email, coalesce(p.emails, true)
           from auth.users u left join public.email_prefs p on p.user_id = u.id
           where u.email is not null and (
             exists (select 1 from public.soirees_choisies s where s.user_id = u.id and s.formule = 'duo')
             or exists (select 1 from public.duo_members m where m.user_id = u.id
                        and (select count(*) from public.duo_members o where o.duo_id = m.duo_id) = 2))"""
    ).fetchall()
    return [Person(email, user_id, emails) for user_id, email, emails in rows]


def busy_days(conn: psycopg.Connection, since: date) -> dict[str, set[date]]:
    """Each account's evening days from `since`: its own and those it is invited to."""
    found: dict[str, set[date]] = {}
    for user_id, day in conn.execute(
        """select s.user_id::text, s.day from public.soirees_choisies s where s.day >= %s
           union select i.user_id::text, s.day from public.soiree_invites i join public.soirees_choisies s on s.id = i.soiree_id where s.day >= %s""",
        (since, since),
    ).fetchall():
        found.setdefault(user_id, set()).add(day)
    return found


def seasons(conn: psycopg.Connection, today: date) -> list[dict[str, Any]]:
    rows = conn.execute("select id, nom, texte, deroule, envies, debut, fin from public.saisons_a_venir(%s)", (today,)).fetchall()
    return [dict(zip(("id", "nom", "texte", "deroule", "envies", "debut", "fin"), row)) for row in rows]


def year_ago(conn: psycopg.Connection, today: date) -> list[dict[str, Any]]:
    """The evenings for two lived a year ago today, with their instigateur and passagers."""
    rows = conn.execute(
        """select s.id, coalesce(s.secret_title, s.title), s.day, s.vibes,
                  json_agg(json_build_object('user_id', u.id::text, 'email', u.email, 'emails', coalesce(p.emails, true)))
           from public.soirees_choisies s
           join lateral (select s.user_id as id union select i.user_id from public.soiree_invites i where i.soiree_id = s.id and i.role = 'passager') who on true
           join auth.users u on u.id = who.id
           left join public.email_prefs p on p.user_id = u.id
           where s.formule = 'duo' and s.day in (%s, %s)
           group by s.id""",
        (today - timedelta(days=365), today - timedelta(days=366)),
    ).fetchall()
    found = []
    for id_, title, day, vibes, people in rows:
        try:
            again = day.replace(year=day.year + 1)
        except ValueError:
            again = date(day.year + 1, 2, 28)
        if again == today:
            found.append({"id": id_, "secret_title": title, "day": day, "envies": vibes, "people": [_person(p) for p in people if p["email"]]})
    return found


Composer = Callable[[str, str, date], str | None]


def compose_for(db: str) -> Composer:
    """Three intrigues for an account on a day, for a kind of date: its profile (else its partner's, else the
    default), its evenings never again, its tastes. The page's name, or None if no evening could be composed."""
    from surprise import quiz  # the server's module, which runs the reminders: imported when first needed
    from surprise.local_store import PostgresStore

    loaded: dict[str, parcours.Base] = {}

    def compose(user_id: str, genre: str, day: date) -> str | None:
        with psycopg.connect(db) as conn:
            row = conn.execute(
                """select coalesce(
                     (select profile from public.couple_profiles where user_id = %(u)s order by created_at desc limit 1),
                     (select c.profile from public.couple_profiles c join public.duo_members m on m.user_id = c.user_id
                      where m.duo_id = (select duo_id from public.duo_members where user_id = %(u)s) and m.user_id <> %(u)s
                      order by c.created_at desc limit 1))""",
                {"u": user_id},
            ).fetchone()
            pages = [p for (p,) in conn.execute("select page_name from public.soirees_choisies where user_id = %s", (user_id,)).fetchall()]
            votes = dict(conn.execute("select activity_id, vote from public.gouts where user_id = %s", (user_id,)).fetchall())
        profile = quiz.valid_profile(row[0]) if row and row[0] else None
        envies, occasion = DATE_WISHES.get(genre, DATE_WISHES["autre"])
        with PostgresStore(db) as store:
            if "base" not in loaded:
                loaded["base"] = parcours.Base.load(store)
            try:
                return quiz.compose(
                    store, loaded["base"], profile or quiz.profile_from({}), envies, days=[day], occasion=occasion, dinner=True,
                    chosen=pages, votes=quiz.valid_votes(votes), checks=0, name_later=False,
                )
            except (ValueError, IndexError):
                return None

    return compose


@dataclass
class Report:
    sent: list[tuple[Moment, str]] = field(default_factory=list)
    failed: list[tuple[Moment, str]] = field(default_factory=list)


def plan(conn: psycopg.Connection, today: date) -> list[Reminder]:
    """Every reminder of the accounts that may fall now."""
    found: list[Reminder] = []
    for duo in duos(conn):
        found += date_reminders(duo, today)
        found += profile_reminders(duo, today)
    found += season_reminders(composers(conn), seasons(conn, today), busy_days(conn, today), today)
    found += anniversary_reminders(year_ago(conn, today), today)
    return found


def run(
    db: str, now: datetime | None = None, *, via: mail.Relay | None = None, firebase: dict[str, Any] | None = None,
    dry_run: bool = False, compose: Composer | None = None,
) -> Report:
    """One pass: every reminder due now, a date's intrigues composed first, emailed and pushed, then noted as sent.
    `compose`: how a date's intrigues are composed (by default quiz.compose on the base). `dry_run`: nothing composed,
    sent nor noted."""
    now = now or datetime.now(PARIS)
    via = via or mail.relay()
    if firebase is None and os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip():
        firebase = push.service_account()
    report = Report()
    with psycopg.connect(db, autocommit=True) as conn:
        today = now.astimezone(PARIS).date()
        due = [r for r in plan(conn, today) if courriers.due(r.moment, now) and r.moment.to.user_id]
        if not due:
            return report
        stopped = {address for (address,) in conn.execute("select address from pipeline.courriels_stop").fetchall()}
        sent = {tuple(row) for row in conn.execute(
            "select user_id::text, cle, recipient from pipeline.rappels where user_id::text = any(%s)",
            ([r.moment.to.user_id for r in due],),
        ).fetchall()}
        letters, pushes = [], []
        for reminder in due:
            person = reminder.moment.to
            email = (person.user_id, reminder.moment.key, person.address) not in sent and person.emails and person.address.lower() not in stopped
            web = (person.user_id, reminder.moment.key, f"push:{person.user_id}") not in sent
            if not (email or web):
                continue
            moment = reminder.moment
            if reminder.compose and not dry_run:
                # The intrigues composed once for the account, kept for the app, the email's button opening them.
                ready = conn.execute("select page_name from public.intrigues_pretes where user_id = %s and cle = %s",
                                     (person.user_id, moment.key)).fetchone()
                page = ready[0] if ready else (compose or compose_for(db))(person.user_id, *reminder.compose)
                if not page:
                    report.failed.append((moment, "aucune intrigue composée"))
                    continue
                if not ready:
                    conn.execute(
                        "insert into public.intrigues_pretes (user_id, cle, page_name, day, label) values (%s, %s, %s, %s, %s) on conflict do nothing",
                        (person.user_id, moment.key, page, reminder.compose[1], moment.subject.split(" approche")[0]),
                    )
                moment = replace(moment, button=(moment.button[0], f"/soiree?soiree={quote(page)}"))
            if email:
                letters.append(moment)
            if web:
                pushes.append(moment)
        if dry_run:
            report.sent = [(m, "email (simulé)") for m in letters] + [(m, "push (simulé)") for m in pushes]
            return report
        if letters and via:
            for moment, (_, why) in zip(letters, mail.send([courriers.letter(m) for m in letters], via)):
                if why:
                    report.failed.append((moment, why))
                    continue
                report.sent.append((moment, "email"))
                _note(conn, moment, moment.to.address)
        if pushes and firebase:
            devices = courriers._web_devices(conn, [m.to.user_id for m in pushes])
            for moment in pushes:
                if not (mine := devices.get(moment.to.user_id)):
                    continue
                told = push.send(mine, moment.subject, moment.push, moment.button[1], account=firebase)
                if gone := [s.device.token for s in told if s.status == "gone"]:
                    push.forget(gone, db)
                if any(s.status == "sent" for s in told):
                    report.sent.append((moment, "push"))
                    _note(conn, moment, f"push:{moment.to.user_id}")
    return report


def _note(conn: psycopg.Connection, moment: Moment, recipient: str) -> None:
    conn.execute(
        "insert into pipeline.rappels (user_id, cle, recipient) values (%s, %s, %s) on conflict do nothing",
        (moment.to.user_id, moment.key, recipient),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Envoie les rappels : dates qui comptent, saisons, il y a un an")
    parser.add_argument("--dry-run", action="store_true", help="montre ce qui partirait maintenant, sans rien composer ni envoyer")
    args = parser.parse_args()
    db = os.environ.get("SUPABASE_DB_URL")
    if not db:
        sys.exit("SUPABASE_DB_URL manque : les comptes sont dans Supabase.")
    sys.stdout.reconfigure(errors="replace")
    report = run(db, dry_run=args.dry_run)
    for moment, channel in report.sent:
        print(f"{channel:15} {moment.to.address:32} {moment.key:32} {moment.subject}")
    for moment, why in report.failed:
        print(f"{'échec':15} {moment.to.address:32} {moment.key:32} {why}")


if __name__ == "__main__":
    main()
