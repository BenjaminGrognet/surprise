"""Push notifications through FCM (surprise.push): the message the app's devices read, Google's token for the service
account, each device told and a token gone forgotten, a test push simulated without a word to FCM. Google and FCM are
stand-ins (respx); the tokens the app keeps are read from the local Supabase (npm run db:start), never the project's."""

import json
import uuid

import httpx
import psycopg
import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.auth import jwt

from surprise import push

LOCAL_DB = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
TOKEN_URI = "https://oauth2.example.com/token"
SEND = push.FCM.format(project="secret-date-test")


@pytest.fixture(scope="module")
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def account(key):
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return {
        "type": "service_account", "project_id": "secret-date-test", "private_key_id": "k1", "private_key": pem.decode(),
        "client_email": "fcm@secret-date-test.iam.gserviceaccount.com", "token_uri": TOKEN_URI,
    }


@pytest.fixture
def google():
    """Google's token endpoint, then FCM: a token it knows, one gone, one it fails on."""
    with respx.mock(assert_all_called=False) as mock:
        mock.post(TOKEN_URI).mock(return_value=httpx.Response(200, json={"access_token": "ya29.test", "expires_in": 3599}))

        def fcm(request: httpx.Request) -> httpx.Response:
            token = json.loads(request.content)["message"]["token"]
            if token.startswith("gone"):
                return httpx.Response(404, json={"error": {"code": 404, "status": "NOT_FOUND", "details": [
                    {"@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError", "errorCode": "UNREGISTERED"}]}})
            if token.startswith("down"):
                return httpx.Response(503, json={"error": {"code": 503, "status": "UNAVAILABLE"}})
            return httpx.Response(200, json={"name": f"projects/secret-date-test/messages/{token}"})

        mock.post(SEND).mock(side_effect=fcm)
        yield mock


def test_the_message_is_read_alike_by_android_and_the_browser():
    sent = push.message("t0", "Secret Date", "Votre soirée approche.", "/revelation?page=soiree-x")
    assert sent == {"message": {
        "token": "t0",
        # expo-notifications (Android) and the site's service worker read the same data: title, message, the page.
        "data": {"title": "Secret Date", "message": "Votre soirée approche.", "body": '{"url": "/revelation?page=soiree-x"}'},
        "android": {"priority": "high"},
        "webpush": {"headers": {"Urgency": "high"}},
    }}
    # FCM takes data as strings only.
    assert all(isinstance(v, str) for v in sent["message"]["data"].values())


def test_each_device_is_told_with_a_token_of_the_service_account(google, account, key):
    devices = [push.Device("web-1", "web"), push.Device("gone-2", "android"), push.Device("down-3", "web")]
    sent = push.send(devices, "Secret Date", "Bonsoir", "/", account=account)
    assert [(s.device.token, s.status) for s in sent] == [("web-1", "sent"), ("gone-2", "gone"), ("down-3", "error")]
    assert sent[0].detail == "projects/secret-date-test/messages/web-1"
    # One token asked of Google for all of them, signed by the service account's key, for FCM only.
    grant = google.calls[0].request
    assert grant.url == TOKEN_URI
    form = dict(httpx.QueryParams(grant.content.decode()))
    assert form["grant_type"] == "urn:ietf:params:oauth:grant-type:jwt-bearer"
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    claims = jwt.decode(form["assertion"], certs=public.decode(), audience=TOKEN_URI)
    assert claims["iss"] == account["client_email"] and claims["scope"] == push.SCOPE
    calls = google.calls[1:]
    assert len(calls) == 3
    assert {c.request.headers["Authorization"] for c in calls} == {"Bearer ya29.test"}
    assert json.loads(calls[0].request.content) == push.message("web-1", "Secret Date", "Bonsoir", "/")


def test_a_simulated_push_tells_nothing_to_fcm():
    with respx.mock(assert_all_mocked=True) as mock:
        sent = push.send([push.Device("web-1", "web")], "Secret Date", "Bonsoir", "/historique", dry_run=True)
        assert not mock.calls
    assert [s.status for s in sent] == ["simulated"]
    assert json.loads(sent[0].detail) == push.message("web-1", "Secret Date", "Bonsoir", "/historique")


def test_the_service_account_is_its_file_or_its_contents(tmp_path, account, monkeypatch):
    path = tmp_path / "secret-date-firebase-adminsdk.json"
    path.write_text(json.dumps(account), encoding="utf-8")
    assert push.service_account(str(path)) == account
    assert push.service_account(json.dumps(account)) == account
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT", raising=False)
    with pytest.raises(SystemExit, match="FIREBASE_SERVICE_ACCOUNT"):
        push.service_account()


@pytest.fixture
def local_db():
    try:
        psycopg.connect(LOCAL_DB, connect_timeout=3).close()
    except psycopg.OperationalError:
        pytest.skip("Supabase local pas lancé : npm run db:start dans app/")
    return LOCAL_DB


@pytest.fixture
def signed_in(local_db):
    """An account of the local Supabase, with the devices it allowed pushes on; another one's beside it."""
    email = f"push-{uuid.uuid4().hex[:8]}@example.com"
    with psycopg.connect(local_db, autocommit=True) as conn:
        users = [conn.execute(
            "insert into auth.users (id, email, aud, role) values (gen_random_uuid(), %s, 'authenticated', 'authenticated') returning id",
            (address,),
        ).fetchone()[0] for address in (email, f"autre-{email}")]
        tag = uuid.uuid4().hex[:6]
        rows = [(f"web-{tag}", users[0], "web", "1 hour"), (f"gone-{tag}", users[0], "android", "2 hours"), (f"other-{tag}", users[1], "web", "0 hours")]
        for token, user, platform, age in rows:
            conn.execute(
                "insert into public.push_tokens (token, user_id, platform, updated_at) values (%s, %s, %s, now() - %s::interval)",
                (token, user, platform, age),
            )
    yield email.upper(), tag
    with psycopg.connect(local_db, autocommit=True) as conn:
        conn.execute("delete from auth.users where id = any(%s)", (users,))


def test_the_test_push_reaches_the_account_s_devices_and_forgets_those_gone(google, account, signed_in, local_db):
    email, tag = signed_in
    assert push.devices_of(email, local_db) == [push.Device(f"web-{tag}", "web"), push.Device(f"gone-{tag}", "android")]

    simulated = push.send_test(email, db=local_db, dry_run=True)
    assert [s.status for s in simulated] == ["simulated", "simulated"]
    assert not google.calls

    sent = push.send_test(email, db=local_db, account=account)
    assert [(s.device.platform, s.status) for s in sent] == [("web", "sent"), ("android", "gone")]
    told = json.loads(google.calls[1].request.content)["message"]
    assert told["data"]["title"] == "Secret Date" and "notification test" in told["data"]["message"]
    # The token gone is forgotten; the other account's devices were never told.
    assert push.devices_of(email, local_db) == [push.Device(f"web-{tag}", "web")]
    assert {json.loads(c.request.content)["message"]["token"] for c in google.calls[1:]} == {f"web-{tag}", f"gone-{tag}"}


def test_no_device_no_push(google, account, local_db):
    assert push.send_test("personne@example.com", db=local_db, account=account) == []
    assert not google.calls
