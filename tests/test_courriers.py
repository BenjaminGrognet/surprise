"""The evenings' emails (surprise.courriers, surprise.mail): who gets which moment and when, each sent once, never at
night but an invitation, never to whom stopped them; the email itself, with its links and the one that stops them;
the SMTP relay; and a whole pass on the local Supabase (npm run db:start), never the project's. The relay is a stand-in."""

import json
import uuid
from datetime import datetime, time, timedelta

import psycopg
import pytest

from serving import serving
from surprise import courriers, mail, parcours, quiz
from surprise.courriers import Evening, Guest, Person
from surprise.local_store import PostgresStore
from test_parcours import DAY, _night
from test_push import account, google, key, local_db  # noqa: F401 (the fixtures)

PARIS = parcours.PARIS


def paris(day_offset, hour, minute=0):
    return datetime.combine(DAY + timedelta(days=day_offset), time(hour, minute), PARIS)


@pytest.fixture(autouse=True)
def links(monkeypatch):
    monkeypatch.setenv("APP_URL", "https://secretdate.example")
    monkeypatch.setenv("MAIL_SECRET", "secret-des-tests")


@pytest.fixture
def route():
    """An evening on DAY from 19:00: a bar walked into, then an immersive show and a club to book."""
    req, _, night = _night()
    return parcours.route_json(0, night, req)


def evening(**changes):
    values = dict(
        id="s1", page_name="soiree-xy", secret_title="Le Pacte du Marais", formule="duo", day=DAY, booked=[], invite_code="abc123",
        chosen_at=paris(-10, 12), instigateur=Person("lea@example.com", "u-lea"), guests=[], later=False,
    )
    return Evening(**(values | changes))


def tom(joined_at=None, **changes):
    return Guest(Person("tom@example.com", "u-tom"), "passager", joined_at or paris(-12, 20), **changes)


def keys(moments, now=None):
    return sorted((m.key, m.to.address) for m in moments if now is None or courriers.due(m, now))


def test_the_instigateur_is_told_the_evening_kept_its_bookings_its_invitation_then_the_morning_after(route):
    moments = courriers.plan(evening(chosen_at=paris(-10, 12)), route)
    assert keys(moments) == [(k, "lea@example.com") for k in ("garde", "invitation", "lendemain", "prochaine", "reservations")]
    garde = next(m for m in moments if m.key == "garde")
    assert garde.subject == "« Le Pacte du Marais » est gardée : vendredi 9 octobre, 19:00"
    # What to book, with its links, and the link to send: in the email kept.
    assert [label for label, _ in garde.links] == ["Expérience immersive", "Soirée techno", "Le lien de l'invitation"]
    assert garde.links[-1][1] == "https://secretdate.example/invitation?code=abc123"
    # The bookings three days before at six, the invitation two days before at half past six, while it makes sense.
    assert keys(moments, paris(-3, 17, 59)) == []
    assert keys(moments, paris(-3, 18)) == [("reservations", "lea@example.com")]
    assert keys(moments, paris(-2, 18, 30)) == [("invitation", "lea@example.com"), ("reservations", "lea@example.com")]
    # Never at night: the moment waits for the morning, if it still can.
    assert keys(moments, paris(-2, 21, 15)) == [] and keys(moments, paris(-1, 9)) == [("invitation", "lea@example.com"), ("reservations", "lea@example.com")]
    assert keys(moments, paris(0, 18)) == []  # the evening is near: past booking now
    # The morning after its end (04:00): the book; three weeks on, the next intrigue.
    assert keys(moments, paris(1, 10, 30)) == [("lendemain", "lea@example.com")]
    assert keys(moments, paris(21, 19, 30)) == [("prochaine", "lea@example.com")]


def test_booked_and_invited_nothing_is_asked_any_more(route):
    booked = [s["id"] for s in route["steps"]]
    moments = courriers.plan(evening(booked=booked, guests=[tom()], later=True), route)
    assert "reservations" not in {m.key for m in moments} and "invitation" not in {m.key for m in moments}
    assert "prochaine" not in {m.key for m in moments}  # another evening of theirs comes after
    garde = next(m for m in moments if m.key == "garde")
    assert garde.links == () and garde.push == "« Le Pacte du Marais » est gardée : tout est prêt."


def test_the_passager_lives_the_sealed_letter_the_eve_the_book_and_their_turn(route):
    moments = [m for m in courriers.plan(evening(guests=[tom()]), route) if m.to.address == "tom@example.com"]
    assert keys(moments) == [(k, "tom@example.com") for k in ("lendemain", "pli", "tour", "veille")]
    pli = next(m for m in moments if m.key == "pli")
    # The day and the hour, nothing of the programme.
    assert pli.lines[0] == "« Le Pacte du Marais » commence vendredi 9 octobre à 19:00. Gardez votre soirée : tout le reste est un secret."
    assert all(step["title"] not in " ".join(m.lines + (m.subject, m.push)) for m in moments for step in route["steps"])
    assert keys(moments, paris(-7, 10)) == [("pli", "tom@example.com")]
    assert keys(moments, paris(-1, 18)) == [("veille", "tom@example.com")]
    assert keys(moments, paris(4, 19)) == [("lendemain", "tom@example.com"), ("tour", "tom@example.com")]
    # Joined three days before: the sealed letter then; composed an evening since: not asked to.
    late = [m for m in courriers.plan(evening(guests=[tom(joined_at=paris(-3, 15), composed_since=True)]), route) if m.to.user_id == "u-tom"]
    assert next(m for m in late if m.key == "pli").at == paris(-3, 15) and "tour" not in {m.key for m in late}


def test_a_bands_complices_book_and_its_words_are_the_bands(route):
    band = evening(formule="squad", guests=[tom(), Guest(Person("ana@example.com", "u-ana"), "complice", paris(-9, 9))])
    moments = courriers.plan(band, route)
    assert keys([m for m in moments if m.to.address == "ana@example.com"]) == [("lendemain", "ana@example.com"), ("reservations", "ana@example.com")]
    tour = next(m for m in moments if m.key == "tour")
    assert "la prochaine virée de la bande" in tour.lines[0]
    book = next(m for m in moments if m.key == "lendemain" and m.to.address == "tom@example.com")
    assert "Celles de la bande se découvrent" in book.lines[0]


def test_an_invitation_by_email_goes_at_once_even_at_night(route):
    row = {"id": "i1", "email": "ami@example.com", "role": "passager", "created_at": paris(-4, 23, 30), "code": "abc123"}
    moment = courriers.invitation_moment(evening(), route, row)
    assert courriers.due(moment, paris(-4, 23, 31)) and not courriers.due(moment, paris(-2, 23, 31))
    assert moment.button == ("Ouvrir mon invitation", "/invitation?code=abc123")
    assert moment.lines[0] == "lea@example.com vous a réservé vendredi 9 octobre à 19:00 : « Le Pacte du Marais »."


def test_the_email_says_it_in_text_and_in_the_brands_colours_with_the_link_that_stops_them(route, monkeypatch):
    moment = next(m for m in courriers.plan(evening(), route) if m.key == "garde")
    letter = courriers.letter(moment)
    token = courriers.token("lea@example.com")
    assert letter.to == "lea@example.com" and letter.subject == moment.subject
    assert letter.unsubscribe == f"https://secretdate.example/api/courriels/stop?stop=lea%40example.com&t={token}"
    for part in (letter.text, letter.html):
        assert "https://secretdate.example/revelation?soiree=soiree-xy" in part
        assert f"https://secretdate.example/compte?stop=lea%40example.com&amp;t={token}" in part or f"compte?stop=lea%40example.com&t={token}" in part
        assert "https://www.billetweb.fr/immersif" in part
    assert "« Le Pacte du Marais »" in letter.html and "<script" not in letter.html
    # Without a secret, no signed link: the account page, where the emails are turned off.
    monkeypatch.delenv("MAIL_SECRET")
    assert courriers.letter(moment).unsubscribe is None and "https://secretdate.example/compte\n" in courriers.letter(moment).text + "\n"
    assert not courriers.signed("lea@example.com", token)


class Relay:
    """An SMTP relay: what it was told, and an address it refuses."""

    def __init__(self, host, port, timeout=None, context=None):
        self.calls = [("connect", host, port, context is not None)]
        self.messages = []
        Relay.last = self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.calls.append(("quit",))

    def starttls(self, context=None):
        self.calls.append(("starttls",))

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def send_message(self, message):
        if message["To"] == "refuse@example.com":
            raise mail.smtplib.SMTPRecipientsRefused({message["To"]: (550, b"no such user")})
        self.messages.append(message)


@pytest.fixture
def relay(monkeypatch):
    monkeypatch.setattr(mail.smtplib, "SMTP", Relay)
    monkeypatch.setattr(mail.smtplib, "SMTP_SSL", Relay)
    monkeypatch.setattr(Relay, "last", None, raising=False)
    return Relay


def test_the_relay_is_its_url_and_sends_each_email_once_connected(relay):
    assert mail.relay("") is None
    via = mail.relay("smtps://lea%40secretdate.fr:mot%20de%20passe@smtp-relay.example.com", "Secret Date <bonjour@secretdate.fr>")
    assert via == mail.Relay("smtp-relay.example.com", 465, True, "lea@secretdate.fr", "mot de passe", "Secret Date <bonjour@secretdate.fr>")
    assert mail.relay("smtp://relay.example.com").port == 587
    with pytest.raises(ValueError, match="SMTP_URL"):
        mail.relay("https://relay.example.com")
    letters = [mail.Letter("lea@example.com", "Bonsoir", "texte", "<p>html</p>", "https://x/stop"), mail.Letter("refuse@example.com", "B", "t", "<p>h</p>")]
    done = mail.send(letters, via)
    assert [why for _, why in done][0] == "" and "SMTPRecipientsRefused" in done[1][1]
    assert relay.last.calls[0] == ("connect", "smtp-relay.example.com", 465, True)
    assert ("login", "lea@secretdate.fr", "mot de passe") in relay.last.calls and ("starttls",) not in relay.last.calls
    [sent] = relay.last.messages
    assert sent["From"] == "Secret Date <bonjour@secretdate.fr>" and sent["List-Unsubscribe"] == "<https://x/stop>"
    assert sent["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert [p.get_content_type() for p in sent.iter_parts()] == ["text/plain", "text/html"]
    # STARTTLS on 587, and an account without password.
    mail.send(letters[:1], mail.relay("smtp://relay.example.com:587"))
    assert relay.last.calls[1] == ("starttls",) and not any(c[0] == "login" for c in relay.last.calls)


# A whole pass on the local Supabase -----------------------------------------------------------


@pytest.fixture
def kept(local_db, route):
    """Léa's evening on DAY, kept ten days before, its route in the pipeline; Tom its passager; an invitation by email
    to a friend asked an hour before the pass; and someone else's evening, never told."""
    tag = uuid.uuid4().hex[:8]
    addresses = {name: f"{name}-{tag}@example.com" for name in ("lea", "tom", "ami", "autre")}
    page = f"soiree-courriers-{tag}"
    req, _, night = _night()
    night.request = req
    with psycopg.connect(local_db, autocommit=True) as conn:
        # Its activities in the pipeline, as collected: a step names one.
        conn.execute("insert into public.sources (id, name, tier) values ('test', 'Test', 3) on conflict do nothing")
        for step in night.steps:
            conn.execute(
                "insert into pipeline.normalized (source_id, external_id, content_hash, activity) values (%s, %s, 'test', %s) on conflict do nothing",
                (*step.candidate.key, json.dumps(step.candidate.item["activity"])),
            )
    with PostgresStore(local_db) as store:
        parcours.save(page, {"routes": [night], "requests": [req], "seen": set()}, store)
    with psycopg.connect(local_db, autocommit=True) as conn:
        ids = {name: conn.execute(
            "insert into auth.users (id, email, aud, role) values (gen_random_uuid(), %s, 'authenticated', 'authenticated') returning id::text",
            (address,),
        ).fetchone()[0] for name, address in addresses.items() if name != "ami"}
        soiree = conn.execute(
            """insert into public.soirees_choisies (user_id, page_name, title, pitch, day, secret_title, chosen_at)
               values (%s, %s, 'Insolite et techno', 'Un soir.', %s, 'Le Pacte du Marais', %s) returning id""",
            (ids["lea"], page, DAY, paris(-10, 12)),
        ).fetchone()[0]
        conn.execute("insert into public.soiree_invites (soiree_id, user_id, email, role, joined_at) values (%s, %s, %s, 'passager', %s)",
                     (soiree, ids["tom"], addresses["tom"], paris(-9, 20)))
        conn.execute("insert into public.email_invitations (soiree_id, email, invited_by, created_at) values (%s, %s, %s, %s)",
                     (soiree, addresses["ami"], ids["lea"], paris(-3, 17, 30)))
    yield {"soiree": soiree, "page": page, "ids": ids, "addresses": addresses}
    with psycopg.connect(local_db, autocommit=True) as conn:
        conn.execute("delete from auth.users where id::text = any(%s)", (list(ids.values()),))
        conn.execute("delete from pipeline.soirees where id = %s", (page,))
        conn.execute("delete from pipeline.courriers where soiree_id = %s", (soiree,))
        conn.execute("delete from pipeline.courriels_stop where address = any(%s)", (list(addresses.values()),))


def test_a_pass_sends_what_is_due_once_and_notes_it(kept, local_db, relay):
    via = mail.relay("smtp://relay.example.com")
    a = kept["addresses"]
    now = paris(-3, 18, 30)
    simulated = courriers.run(local_db, now, via=via, dry_run=True)
    assert sorted((m.key, m.to.address) for m, _ in simulated.sent) == sorted([
        ("reservations", a["lea"]), ("pli", a["tom"]), (f"invitation-email:{_invitation(local_db, kept)}", a["ami"]),
        ("reservations", a["lea"]), ("pli", a["tom"]),  # their pushes, would they have a browser
    ])
    assert relay.last is None  # nothing sent, nothing noted

    report = courriers.run(local_db, now, via=via)
    assert sorted((m.key, m.to.address, channel) for m, channel in report.sent) == sorted([
        ("reservations", a["lea"], "email"), ("pli", a["tom"], "email"), (f"invitation-email:{_invitation(local_db, kept)}", a["ami"], "email"),
    ])
    told = {m["To"]: m for m in relay.last.messages}
    assert "Encore 2 réservations pour « Le Pacte du Marais »" == told[a["lea"]]["Subject"]
    assert "invitation?code=" in told[a["ami"]].get_body(("plain",)).get_content()
    # Noted: the next pass sends nothing again; the invitation marked sent.
    assert courriers.run(local_db, now + timedelta(minutes=10), via=via).sent == []
    with psycopg.connect(local_db) as conn:
        assert conn.execute("select sent_at is not null from public.email_invitations where soiree_id = %s", (kept["soiree"],)).fetchone() == (True,)


def test_whoever_stopped_them_gets_no_more_emails(kept, local_db, relay):
    a = kept["addresses"]
    courriers.stop(local_db, a["tom"].upper())
    report = courriers.run(local_db, paris(-1, 18, 15), via=mail.relay("smtp://relay.example.com"))
    # The eve was Tom's: only Léa's bookings go.
    assert [(m.key, m.to.address) for m, _ in report.sent] == [("reservations", a["lea"])]
    with psycopg.connect(local_db) as conn:
        assert conn.execute("select emails from public.email_prefs where user_id = %s", (kept["ids"]["tom"],)).fetchone() == (False,)


def test_the_link_of_an_email_stops_them_from_the_app_or_in_one_click(kept, local_db, monkeypatch):
    a = kept["addresses"]
    monkeypatch.setattr(parcours, "DB", None)  # make_handler sets it: put back after
    with serving(quiz.make_handler(local_db, checks=0)) as url:
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        def post(path, body, kind="application/json"):
            try:
                return urlopen(Request(url + path, data=body, headers={"Content-Type": kind})).status
            except HTTPError as error:
                return error.code

        assert post("/api/courriels/stop", b'{"stop": "%s", "t": "faux"}' % a["tom"].encode()) == 403
        assert post("/api/courriels/stop", b'{"stop": "%s", "t": "%s"}' % (a["tom"].encode(), courriers.token(a["tom"]).encode())) == 200
        one_click = f"/api/courriels/stop?stop={a['ami']}&t={courriers.token(a['ami'])}"
        assert post(one_click, b"List-Unsubscribe=One-Click", "application/x-www-form-urlencoded") == 200
    with psycopg.connect(local_db) as conn:
        stopped = {address for (address,) in conn.execute("select address from pipeline.courriels_stop where address = any(%s)", ([a["tom"], a["ami"]],))}
    assert stopped == {a["tom"], a["ami"]}


def test_the_browsers_that_allowed_it_get_the_moment_too_not_the_phones(kept, local_db, relay, google, account):
    ids, tag = kept["ids"], uuid.uuid4().hex[:6]
    with psycopg.connect(local_db, autocommit=True) as conn:
        for token, user, platform in ((f"web-{tag}", ids["lea"], "web"), (f"android-{tag}", ids["lea"], "android"), (f"gone-{tag}", ids["tom"], "web")):
            conn.execute("insert into public.push_tokens (token, user_id, platform) values (%s, %s, %s)", (token, user, platform))
    report = courriers.run(local_db, paris(-3, 18, 30), firebase=account)  # no relay: the pushes only
    assert sorted((m.key, channel) for m, channel in report.sent) == [("reservations", "push")]
    told = [json.loads(call.request.content)["message"] for call in google.calls if call.request.url.host == "fcm.googleapis.com"]
    assert {m["token"] for m in told} == {f"web-{tag}", f"gone-{tag}"}  # the browsers, never the Android phone
    lea = next(m for m in told if m["token"] == f"web-{tag}")
    assert lea["data"]["title"] == "Encore 2 réservations pour « Le Pacte du Marais »"
    assert json.loads(lea["data"]["body"])["url"] == f"/revelation?soiree={kept['page']}"
    # Tom's browser gone: forgotten, and his letter not noted (it goes by email).
    with psycopg.connect(local_db) as conn:
        assert conn.execute("select count(*) from public.push_tokens where token = %s", (f"gone-{tag}",)).fetchone() == (0,)
    assert courriers.run(local_db, paris(-3, 18, 40), firebase=account).sent == []


def _invitation(db, kept):
    with psycopg.connect(db) as conn:
        return conn.execute("select id::text from public.email_invitations where soiree_id = %s", (kept["soiree"],)).fetchone()[0]
