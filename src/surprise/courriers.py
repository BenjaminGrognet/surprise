"""Emails beside the phone's notifications: the key moments of each kept evening, by email to its accounts, and the
invitations an instigateur sends by email from the app; on the web, the same moments pushed to the browsers that
allowed them (surprise.push), where the phone's own notifications never ring. Plain rules, like the phone's story
(app/src/lib/story.ts), on the evenings kept in Supabase (SUPABASE_DB_URL):

- the instigateur: the evening kept (its bookings, with their links, and its invitation link), the bookings still to
  make three days before, the invitation still to send two days before, the Livre des Secrets the morning after, the
  next intrigue three weeks on (unless another evening is kept);
- each passager: the sealed letter a week before (the day and hour, nothing else; at once if they join later), the
  eve, the Livre des Secrets, and four days after, their turn to surprise (unless they composed one since);
- a band's complices: the bookings still to make, and the Livre des Secrets;
- an address given in the app: its invitation, at once.

Each moment goes once (pipeline.courriers), between 9:00 and 21:00 but for an invitation, while it still makes sense;
never to an account that stopped them (public.email_prefs) nor to an address stopped from an email's link
(pipeline.courriels_stop). Links lead to the app (APP_URL); the link that stops them is signed with MAIL_SECRET.

    uv run --env-file .env python -m surprise.courriers --dry-run     # what would go now, nothing sent
    uv run --env-file .env python -m surprise.courriers               # sends it (SMTP_URL, surprise.mail)
    uv run --env-file .env python -m surprise.courriers --loop 10     # again every ten minutes
"""

import argparse
import hashlib
import hmac
import html
import json
import os
import sys
import time as clock
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from urllib.parse import quote

import psycopg

from surprise import mail, parcours, push
from surprise.local_store import PostgresStore

PARIS = parcours.PARIS
QUIET_FROM, QUIET_TO = time(21), time(9)
# Evenings read: those of the last four weeks (the next intrigue) and of the coming month.
PAST_DAYS, AHEAD_DAYS = 29, 31
DEFAULT_APP = "http://127.0.0.1:8001"
_DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


@dataclass(frozen=True)
class Person:
    address: str
    user_id: str | None = None  # an account; None for an address invited by email
    emails: bool = True  # its choice in the app (public.email_prefs)


@dataclass(frozen=True)
class Guest:
    person: Person
    role: str  # passager, complice
    joined_at: datetime
    composed_since: bool = False  # an evening of their own kept after this one


@dataclass
class Evening:
    """A kept evening as the emails read it: its row in public.soirees_choisies, its people."""

    id: str
    page_name: str
    secret_title: str
    formule: str
    day: date
    booked: list[str]
    invite_code: str
    chosen_at: datetime
    instigateur: Person
    guests: list[Guest] = field(default_factory=list)
    later: bool = False  # another evening of the instigateur's comes after this one

    @property
    def squad(self) -> bool:
        return self.formule == "squad"


@dataclass(frozen=True)
class Moment:
    """One email, and its push on the web: who, when (from `at`, while before `until`), what it says, where it leads."""

    key: str
    to: Person
    at: datetime
    until: datetime
    subject: str
    lines: tuple[str, ...]
    button: tuple[str, str]  # label, the app's page
    push: str
    links: tuple[tuple[str, str], ...] = ()  # (label, address): the bookings to make, the invitation link
    anytime: bool = False  # asked just now: not held back until the morning


def long_day(day: date) -> str:
    return f"{_DAYS[day.weekday()]} {day.day}{'er' if day.day == 1 else ''} {_MONTHS[day.month - 1]}"


def hour(moment: datetime) -> str:
    return f"{moment.astimezone(PARIS):%H:%M}"


def _local(day: date, offset: int, at: time) -> datetime:
    return datetime.combine(day + timedelta(days=offset), at, PARIS)


def app_url() -> str:
    return (os.environ.get("APP_URL") or DEFAULT_APP).rstrip("/")


def _revelation(evening: Evening) -> str:
    return f"/revelation?soiree={quote(evening.page_name)}"


def _book(evening: Evening) -> str:
    return f"/livre?soiree={quote(evening.page_name)}"


def _invitation(code: str) -> str:
    return f"/invitation?code={quote(code)}"


def _to_book(evening: Evening, route: dict[str, Any]) -> list[dict[str, Any]]:
    """The steps still to book, as the instigateur's page lists them (a night's room too)."""
    steps = [*route["steps"], *([route["night"]] if route.get("night") else [])]
    return [s for s in steps if s.get("booking_action") == "reserver" and s.get("booking_url") and s["id"] not in evening.booked]


def _bookings(count: int) -> str:
    return f"{count} réservation{'s' if count > 1 else ''}"


def plan(evening: Evening, route: dict[str, Any]) -> list[Moment]:
    """Every moment of the evening, whenever it falls: `due` tells those to send now."""
    start, end = datetime.fromisoformat(route["start"]), datetime.fromisoformat(route["end"])
    day, at = evening.day, hour(start)
    secret = evening.secret_title or "Votre soirée"
    first = route["steps"][0]
    to_book = _to_book(evening, route)
    bookings = tuple((s["title"], s["booking_url"]) for s in to_book)
    invitation = (("Le lien de l'invitation", app_url() + _invitation(evening.invite_code)),)
    band, guest = ("votre bande", "Votre bande") if evening.squad else ("votre passager", "Votre passager")
    morning_after = max(_local(day, 1, time(10, 30)), end + timedelta(hours=3))
    moments = []
    me = evening.instigateur

    # The instigateur's.
    steps = len(route["steps"])
    lines = [f"Votre intrigue est prête : {steps} étape{'s' if steps > 1 else ''} {long_day(day)}, premier rendez-vous à {at} ({first['title']})."]
    links = ()
    if to_book:
        lines.append("À réserver dès maintenant, les places partent vite :")
        links = bookings
    if not evening.guests:
        lines.append(f"{guest} n'a pas encore son invitation : envoyez-lui le lien de la soirée, il n'en recevra que les indices."
                     if not evening.squad else "Votre bande n'a pas encore son invitation : envoyez-lui le lien, chacun n'en recevra que les indices.")
        links += invitation
    moments.append(Moment(
        "garde", me, evening.chosen_at, min(evening.chosen_at + timedelta(days=2), start), f"« {secret} » est gardée : {long_day(day)}, {at}",
        tuple(lines), ("Ouvrir la feuille de route", _revelation(evening)),
        f"« {secret} » est gardée : {_bookings(len(to_book))} à faire." if to_book else f"« {secret} » est gardée : tout est prêt.", links,
    ))
    bookers = [me, *(g.person for g in evening.guests if g.role == "complice")]
    if to_book:
        for person in bookers:
            moments.append(Moment(
                "reservations", person, _local(day, -3, time(18)), start - timedelta(hours=4), f"Encore {_bookings(len(to_book))} pour « {secret} »",
                (f"{long_day(day).capitalize()} approche : il reste {_bookings(len(to_book))} à faire.",), ("Cocher mes réservations", _revelation(evening)),
                f"Encore {_bookings(len(to_book))} à faire : {', '.join(s['title'] for s in to_book)}.", bookings,
            ))
    if not evening.guests:
        moments.append(Moment(
            "invitation", me, _local(day, -2, time(18, 30)), start - timedelta(hours=2), f"{guest} n'a pas encore son invitation",
            (f"Sans elle, pas d'indices : envoyez à {band} le lien de « {secret} ».",), ("Envoyer l'invitation", _revelation(evening)),
            f"{guest} n'a pas encore son invitation : sans elle, pas d'indices.", invitation,
        ))
    others = "Celles de la bande se découvrent" if evening.squad else "Celle de votre complice se découvre"
    for person in bookers:
        moments.append(Moment(
            "lendemain", person, morning_after, _local(day, 5, time(21)), f"Le Livre des Secrets de « {secret} »",
            (f"Scellez votre page d'hier soir : une photo, un mot. {others} quand vous scellez la vôtre.",
             *(("D'un pouce sur chaque étape, dites ce qui vous a plu : la prochaine soirée en tiendra compte.",) if person == me else ())),
            ("Sceller ma page", _book(evening)), "Une page vous attend : une photo, un mot sur hier soir.",
        ))
    if not evening.later:
        moments.append(Moment(
            "prochaine", me, _local(day, 21, time(19)), _local(day, 28, time(21)), f"Trois semaines depuis « {secret} »",
            ("Une nouvelle soirée ? Vos pouces guident la suivante, et le secret reste entier.",),
            ("Tramer une nouvelle intrigue", "/soiree"), f"Trois semaines depuis « {secret} ». Une nouvelle soirée ?",
        ))

    # Each passager's.
    for passager in (g for g in evening.guests if g.role == "passager"):
        person = passager.person
        moments += [
            Moment(
                "pli", person, max(_local(day, -7, time(10)), passager.joined_at), _local(day, -1, time(12)), "Un pli scellé pour vous",
                (f"« {secret} » commence {long_day(day)} à {at}. Gardez votre soirée : tout le reste est un secret.",
                 "Chaque matin, un indice vous attend ; le jour J, chaque étape se dévoile peu avant son heure."),
                ("Voir mes indices", _revelation(evening)), f"« {secret} » commence {long_day(day)} à {at}. Tout le reste est un secret.",
            ),
            Moment(
                "veille", person, _local(day, -1, time(18)), start - timedelta(hours=3), f"Demain, {at}",
                (f"« {secret} » commence demain à {at}. Les derniers indices tombent au fil de la journée.",),
                ("Voir mes indices", _revelation(evening)), f"Demain, {at}. Les derniers indices tombent au fil de la journée.",
            ),
            Moment(
                "lendemain", person, morning_after, _local(day, 5, time(21)), f"Le Livre des Secrets de « {secret} »",
                (f"Une page vous attend : une photo, un mot sur hier soir. {others} quand vous scellez la vôtre.",),
                ("Sceller ma page", _book(evening)), "Une page vous attend : une photo, un mot sur hier soir.",
            ),
        ]
        if not passager.composed_since:
            moments.append(Moment(
                "tour", person, _local(day, 4, time(19)), _local(day, 10, time(21)), "À votre tour de surprendre",
                ("Et si la prochaine virée de la bande, c'était vous qui la gardiez secrète ? Composez-la : ils n'en verront que les indices."
                 if evening.squad else
                 "Et si, la prochaine fois, c'était vous qui gardiez le secret ? Composez une soirée : votre complice n'en verra que les indices.",),
                ("Composer une soirée", "/soiree"), "À votre tour de surprendre : composez une soirée, l'autre n'en verra que les indices.",
            ))
    return moments


def invitation_moment(evening: Evening, route: dict[str, Any], row: dict[str, Any]) -> Moment:
    """An invitation sent by email from the app, to the address given: the evening's day and hour, its link."""
    start = datetime.fromisoformat(route["start"])
    secret = evening.secret_title or "une soirée secrète"
    complice = row["role"] == "complice"
    code = row["code"]
    lines = [f"{evening.instigateur.address} vous a réservé {long_day(evening.day)} à {hour(start)} : « {secret} »."]
    lines.append(
        "Vous êtes dans la confidence : vous verrez tout le programme et cocherez les réservations avec l'organisateur."
        if complice else
        "Vous n'en saurez pas plus… sinon un indice chaque matin. Créez votre compte en un instant pour les recevoir : rien ne vous sera dévoilé avant l'heure.")
    brand = "Secret Squad" if evening.squad else "Secret Date"
    return Moment(
        f"invitation-email:{row['id']}", Person(row["email"]), row["created_at"], min(row["created_at"] + timedelta(days=2), start),
        f"Une soirée secrète vous attend sur {brand}", tuple(lines), ("Ouvrir mon invitation", _invitation(code)),
        "", anytime=True,
    )


def due(moment: Moment, now: datetime) -> bool:
    """To send now: its time come and not gone, and, but for an invitation, in the day (9:00 to 21:00 in Paris)."""
    if not moment.at <= now < moment.until:
        return False
    return moment.anytime or QUIET_TO <= now.astimezone(PARIS).time() < QUIET_FROM


# Signed links ----------------------------------------------------------------


def secret() -> bytes | None:
    value = os.environ.get("MAIL_SECRET", "").strip()
    return value.encode() if value else None


def token(address: str, key: bytes | None = None) -> str | None:
    """The signature of an address's link that stops its emails; None without MAIL_SECRET."""
    key = key or secret()
    return hmac.new(key, address.strip().lower().encode(), hashlib.sha256).hexdigest()[:32] if key else None


def signed(address: str, given: str) -> bool:
    expected = token(address)
    return bool(expected and given) and hmac.compare_digest(expected, given)


def stop_links(address: str) -> tuple[str, str | None]:
    """The app's page that stops the emails (signed when it can be), and the one-click link mail clients use."""
    if not (signature := token(address)):
        return app_url() + "/compte", None
    query = f"stop={quote(address)}&t={signature}"
    return f"{app_url()}/compte?{query}", f"{app_url()}/api/courriels/stop?{query}"


# The email itself ------------------------------------------------------------

_NIGHT, _CARD, _GOLD, _IVORY, _SAGE = "#040F0A", "#081A13", "#DBC18C", "#E9E5D8", "#8F9E91"


def letter(moment: Moment, squad: bool = False) -> mail.Letter:
    """The email of a moment: its text, and the same in the brand's night and gold."""
    brand = "Secret Squad" if squad else "Secret Date"
    page, one_click = stop_links(moment.to.address)
    why = ("Vous recevez cet email parce que vous avez un compte Secret Date." if moment.to.user_id
           else "Vous recevez cet email parce qu'on vous a invité·e à une soirée Secret Date.")
    button = app_url() + moment.button[1]
    text = "\n\n".join([
        *moment.lines,
        *(f"- {label} : {url}" for label, url in moment.links),
        f"{moment.button[0]} : {button}",
        f"—\n{why}\nNe plus recevoir ces emails : {page}",
    ])
    esc = html.escape
    paragraphs = "".join(f'<p style="margin:0 0 14px">{esc(line)}</p>' for line in moment.lines)
    links = "".join(
        f'<li style="margin:0 0 8px"><a href="{esc(url)}" style="color:{_GOLD}">{esc(label)}</a></li>' for label, url in moment.links
    )
    body = f"""<!doctype html><html lang="fr"><body style="margin:0;padding:0;background:{_NIGHT}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{_NIGHT};padding:32px 12px">
<tr><td align="center"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:{_CARD};border:1px solid rgba(219,193,140,.28);border-radius:22px">
<tr><td style="padding:28px 28px 8px;font-family:Georgia,'Times New Roman',serif;color:{_GOLD};font-size:13px;letter-spacing:3px;text-transform:uppercase">{esc(brand)}</td></tr>
<tr><td style="padding:0 28px 6px;font-family:Georgia,'Times New Roman',serif;font-style:italic;color:{_IVORY};font-size:26px;line-height:32px">{esc(moment.subject)}</td></tr>
<tr><td style="padding:14px 28px 0;font-family:Helvetica,Arial,sans-serif;color:{_IVORY};font-size:15px;line-height:22px">{paragraphs}
{f'<ul style="padding-left:18px;margin:0 0 14px">{links}</ul>' if links else ''}</td></tr>
<tr><td style="padding:6px 28px 28px"><a href="{esc(button)}" style="display:inline-block;background:{_GOLD};color:{_NIGHT};font-family:Helvetica,Arial,sans-serif;font-size:15px;font-weight:bold;text-decoration:none;padding:13px 24px;border-radius:999px">{esc(moment.button[0])}</a></td></tr>
</table>
<p style="max-width:520px;font-family:Helvetica,Arial,sans-serif;color:{_SAGE};font-size:12px;line-height:18px;margin:16px auto 0">{esc(why)}
<a href="{esc(page)}" style="color:{_SAGE}">Ne plus recevoir ces emails</a></p>
</td></tr></table></body></html>"""
    return mail.Letter(moment.to.address, moment.subject, text, body, one_click)


# The evenings, from Supabase ---------------------------------------------------

_EVENINGS = """
select s.id, s.page_name, coalesce(s.secret_title, s.title), s.formule, s.day, s.booked, s.invite_code, s.chosen_at,
       s.user_id::text, u.email, coalesce(p.emails, true),
       exists (select 1 from public.soirees_choisies o where o.user_id = s.user_id and o.day > s.day),
       coalesce((
         select json_agg(json_build_object(
           'user_id', i.user_id::text, 'email', coalesce(iu.email, i.email), 'role', i.role, 'joined_at', i.joined_at,
           'emails', coalesce(ip.emails, true),
           'composed_since', exists (select 1 from public.soirees_choisies o where o.user_id = i.user_id and o.day > s.day)))
         from public.soiree_invites i
         join auth.users iu on iu.id = i.user_id
         left join public.email_prefs ip on ip.user_id = i.user_id
         where i.soiree_id = s.id), '[]')
from public.soirees_choisies s
join auth.users u on u.id = s.user_id
left join public.email_prefs p on p.user_id = s.user_id
where s.day between %s and %s
"""


def evenings(conn: psycopg.Connection, today: date) -> list[Evening]:
    rows = conn.execute(_EVENINGS, (today - timedelta(days=PAST_DAYS), today + timedelta(days=AHEAD_DAYS))).fetchall()
    found = []
    for id_, page, secret_title, formule, day, booked, code, chosen_at, user_id, email, emails, later, guests in rows:
        if not email:
            continue
        guests = json.loads(guests) if isinstance(guests, str) else guests
        found.append(Evening(
            id_, page, secret_title, formule, day, list(booked or []), code, chosen_at, Person(email, user_id, emails),
            [Guest(Person(g["email"], g["user_id"], g["emails"]), g["role"], datetime.fromisoformat(g["joined_at"]), g["composed_since"])
             for g in guests if g.get("email")],
            later,
        ))
    return found


def invitations(conn: psycopg.Connection, now: datetime) -> list[dict[str, Any]]:
    """The invitations asked by email and not sent yet, at most two days before `now`, with their evening's link
    (passagers' or complices')."""
    rows = conn.execute(
        """select i.id::text, i.soiree_id, i.email, i.role, i.created_at,
                  case when i.role = 'complice' then c.complice_code else s.invite_code end
           from public.email_invitations i
           join public.soirees_choisies s on s.id = i.soiree_id
           left join public.soiree_codes c on c.soiree_id = s.id
           where i.sent_at is null and i.created_at > %s - interval '2 days'""",
        (now,),
    ).fetchall()
    return [dict(zip(("id", "soiree_id", "email", "role", "created_at", "code"), row)) for row in rows]


@dataclass
class Report:
    sent: list[tuple[Moment, str]] = field(default_factory=list)  # (moment, channel: email or push)
    failed: list[tuple[Moment, str]] = field(default_factory=list)  # (moment, why)


def run(db: str, now: datetime | None = None, *, via: mail.Relay | None = None, firebase: dict[str, Any] | None = None, dry_run: bool = False) -> Report:
    """One pass: every moment due now, emailed and pushed to the browsers that allowed them, then noted as sent.
    `via`: the SMTP relay (else SMTP_URL; without one, no email); `firebase`: the service account (else
    FIREBASE_SERVICE_ACCOUNT; without one, no push). `dry_run`: nothing sent nor noted."""
    now = now or datetime.now(PARIS)
    via = via or mail.relay()
    if firebase is None and os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip():
        firebase = push.service_account()
    report = Report()
    with psycopg.connect(db, autocommit=True) as conn, PostgresStore(db) as store:
        kept = evenings(conn, now.astimezone(PARIS).date())
        stopped = {address for (address,) in conn.execute("select address from pipeline.courriels_stop").fetchall()}
        sent = {tuple(row) for row in conn.execute(
            "select soiree_id, moment, recipient from pipeline.courriers where soiree_id = any(%s)", ([e.id for e in kept],),
        ).fetchall()}
        routes: dict[str, dict[str, Any] | None] = {}

        def route_of(evening: Evening) -> dict[str, Any] | None:
            if evening.page_name not in routes:
                state = parcours.load(evening.page_name, store)
                routes[evening.page_name] = (
                    parcours.route_json(0, state["routes"][0], state["requests"][0], evening.page_name) if state and state["routes"] else None
                )
            return routes[evening.page_name]

        letters: list[tuple[Evening, Moment]] = []
        pushes: list[tuple[Evening, Moment]] = []
        for evening in kept:
            if not (route := route_of(evening)):
                continue
            for moment in plan(evening, route):
                if not due(moment, now):
                    continue
                person = moment.to
                if (evening.id, moment.key, person.address) not in sent and person.emails and person.address.lower() not in stopped:
                    letters.append((evening, moment))
                if person.user_id and (evening.id, moment.key, f"push:{person.user_id}") not in sent:
                    pushes.append((evening, moment))
        by_id = {e.id: e for e in kept}
        for row in invitations(conn, now):
            evening = by_id.get(row["soiree_id"])
            if evening and (route := route_of(evening)) and row["code"] and row["email"].lower() not in stopped:
                moment = invitation_moment(evening, route, row)
                if due(moment, now):
                    letters.append((evening, moment))

        if dry_run:
            report.sent = [(m, "email (simulé)") for _, m in letters] + [(m, "push (simulé)") for _, m in pushes]
            return report
        if letters and via:
            for (evening, moment), (_, why) in zip(letters, mail.send([letter(m, e.squad) for e, m in letters], via)):
                if why:
                    report.failed.append((moment, why))
                    continue
                report.sent.append((moment, "email"))
                _note(conn, evening.id, moment, moment.to.address)
        if pushes and firebase:
            devices = _web_devices(conn, [m.to.user_id for _, m in pushes])
            for evening, moment in pushes:
                if not (mine := devices.get(moment.to.user_id)):
                    continue
                told = push.send(mine, moment.subject, moment.push, moment.button[1], account=firebase)
                if gone := [s.device.token for s in told if s.status == "gone"]:
                    push.forget(gone, db)
                if any(s.status == "sent" for s in told):
                    report.sent.append((moment, "push"))
                    _note(conn, evening.id, moment, f"push:{moment.to.user_id}")
    return report


def _note(conn: psycopg.Connection, soiree_id: str, moment: Moment, recipient: str) -> None:
    if moment.key.startswith("invitation-email:"):
        conn.execute("update public.email_invitations set sent_at = now() where id = %s", (moment.key.split(":", 1)[1],))
    conn.execute(
        "insert into pipeline.courriers (soiree_id, moment, recipient) values (%s, %s, %s) on conflict do nothing",
        (soiree_id, moment.key, recipient),
    )


def _web_devices(conn: psycopg.Connection, users: list[str | None]) -> dict[str, list[push.Device]]:
    """The browsers each account allowed pushes on: the phones have their own notifications."""
    found: dict[str, list[push.Device]] = {}
    for user, token_, platform in conn.execute(
        "select user_id::text, token, platform from public.push_tokens where platform = 'web' and user_id::text = any(%s)", ([u for u in users if u],),
    ).fetchall():
        found.setdefault(user, []).append(push.Device(token_, platform))
    return found


def stop(db: str, address: str) -> None:
    """No more emails to this address: an account's choice turned off too."""
    address = address.strip().lower()
    with psycopg.connect(db, autocommit=True) as conn:
        conn.execute("insert into pipeline.courriels_stop (address) values (%s) on conflict do nothing", (address,))
        conn.execute(
            """insert into public.email_prefs (user_id, emails, updated_at)
               select id, false, now() from auth.users where lower(email) = %s
               on conflict (user_id) do update set emails = false, updated_at = now()""",
            (address,),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Envoie les emails (et les pushes web) des soirées gardées")
    parser.add_argument("--dry-run", action="store_true", help="montre ce qui partirait maintenant, sans rien envoyer")
    parser.add_argument("--loop", type=float, metavar="MINUTES", help="recommence toutes les MINUTES minutes")
    args = parser.parse_args()
    db = os.environ.get("SUPABASE_DB_URL")
    if not db:
        sys.exit("SUPABASE_DB_URL manque : les soirées et les comptes sont dans Supabase.")
    sys.stdout.reconfigure(errors="replace")
    if not args.dry_run and not mail.relay():
        print("SMTP_URL manque : aucun email ne partira (les pushes web, si FIREBASE_SERVICE_ACCOUNT est là).")
    while True:
        report = run(db, dry_run=args.dry_run)
        for moment, channel in report.sent:
            print(f"{channel:15} {moment.to.address:32} {moment.key:18} {moment.subject}")
        for moment, why in report.failed:
            print(f"{'échec':15} {moment.to.address:32} {moment.key:18} {why}")
        if not args.loop:
            break
        clock.sleep(args.loop * 60)


if __name__ == "__main__":
    main()
