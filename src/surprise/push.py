"""Push notifications through Firebase Cloud Messaging (its HTTP v1 API), to the devices an account allowed them on:
the browser or the Android phone whose FCM token the app keeps for it (public.push_tokens, app/src/lib/push.ts). A
token FCM no longer knows (the app uninstalled, the site's permission withdrawn) is forgotten. A test push, to try it.

The Firebase project's service account (console › Project settings › Service accounts › Generate new private key) in
FIREBASE_SERVICE_ACCOUNT, the JSON file's path or its contents; the tokens read from Supabase (SUPABASE_DB_URL).

    uv run --env-file .env python -m surprise.push vous@exemple.fr            # a test push to each of its devices
    uv run --env-file .env python -m surprise.push vous@exemple.fr --dry-run  # simulated: what FCM would be sent
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import psycopg
from google.auth import crypt, jwt

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FCM = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"
TEST = {
    "title": "Secret Date",
    "text": "Ceci est une notification test : vos notifications arrivent bien sur cet appareil.",
    "url": "/",
}


@dataclass(frozen=True)
class Device:
    token: str
    platform: str  # web, android


@dataclass(frozen=True)
class Sent:
    device: Device
    status: str  # sent, simulated, gone (forgotten), error
    detail: str = ""


def service_account(value: str | None = None) -> dict[str, Any]:
    """The service account's JSON key, from FIREBASE_SERVICE_ACCOUNT: its contents, or its file's path."""
    value = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "") if value is None else value
    if not value.strip():
        raise SystemExit("FIREBASE_SERVICE_ACCOUNT manque : la clé JSON du compte de service Firebase, ou son chemin.")
    return json.loads(value if value.lstrip().startswith("{") else Path(value).read_text(encoding="utf-8"))


def message(token: str, title: str, text: str, url: str = "/") -> dict[str, Any]:
    """An FCM message as expo-notifications shows it on Android, and the site's service worker on the web
    (app/public/firebase-messaging-sw.js): data only, the page to open in its body."""
    return {
        "message": {
            "token": token,
            "data": {"title": title, "message": text, "body": json.dumps({"url": url})},
            "android": {"priority": "high"},
            "webpush": {"headers": {"Urgency": "high"}},
        }
    }


def access_token(account: dict[str, Any], client: httpx.Client) -> str:
    """An OAuth token for FCM, an hour long: the service account's signed assertion, exchanged at Google's."""
    now = int(time.time())
    claims = {"iss": account["client_email"], "scope": SCOPE, "aud": account["token_uri"], "iat": now, "exp": now + 3600}
    assertion = jwt.encode(crypt.RSASigner.from_service_account_info(account), claims).decode()
    response = client.post(
        account["token_uri"], data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _gone(response: httpx.Response) -> bool:
    """FCM no longer knows the token: UNREGISTERED (404), or a token that never was one."""
    if response.status_code == 404:
        return True
    error = response.json().get("error", {}) if response.headers.get("content-type", "").startswith("application/json") else {}
    codes = {d.get("errorCode") for d in error.get("details", [])}
    return "UNREGISTERED" in codes or (response.status_code == 400 and "registration token" in error.get("message", ""))


def send(
    devices: list[Device], title: str, text: str, url: str = "/", *,
    account: dict[str, Any] | None = None, dry_run: bool = False,
) -> list[Sent]:
    """The push to each device; simulated (`dry_run`): nothing sent, the request each would be told."""
    if dry_run:
        return [Sent(d, "simulated", json.dumps(message(d.token, title, text, url), ensure_ascii=False)) for d in devices]
    if not devices:
        return []
    account = account or service_account()
    sent = []
    with httpx.Client(timeout=20) as client:
        headers = {"Authorization": f"Bearer {access_token(account, client)}"}
        for device in devices:
            response = client.post(FCM.format(project=account["project_id"]), headers=headers, json=message(device.token, title, text, url))
            if response.is_success:
                sent.append(Sent(device, "sent", response.json().get("name", "")))
            else:
                sent.append(Sent(device, "gone" if _gone(response) else "error", f"{response.status_code} {response.text[:200]}"))
    return sent


def devices_of(email: str, db: str) -> list[Device]:
    """The devices the account allowed pushes on, the latest first."""
    with psycopg.connect(db) as conn:
        rows = conn.execute(
            "select t.token, t.platform from public.push_tokens t join auth.users u on u.id = t.user_id"
            " where lower(u.email) = lower(%s) order by t.updated_at desc",
            (email.strip(),),
        ).fetchall()
    return [Device(token, platform) for token, platform in rows]


def forget(tokens: list[str], db: str) -> None:
    with psycopg.connect(db) as conn:
        conn.execute("delete from public.push_tokens where token = any(%s)", (tokens,))


def send_test(email: str, *, db: str | None = None, dry_run: bool = False, account: dict[str, Any] | None = None) -> list[Sent]:
    """The test push to each of the account's devices (simulated with `dry_run`); the tokens gone, forgotten."""
    db = db or os.environ.get("SUPABASE_DB_URL")
    if not db:
        raise SystemExit("SUPABASE_DB_URL manque : la base où l'app garde les jetons des appareils.")
    sent = send(devices_of(email, db), TEST["title"], TEST["text"], TEST["url"], account=account, dry_run=dry_run)
    if gone := [s.device.token for s in sent if s.status == "gone"]:
        forget(gone, db)
    return sent


SAID = {"sent": "envoyée", "simulated": "simulée", "gone": "jeton périmé, oublié", "error": "erreur"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Envoie une notification push test (FCM) aux appareils d'un compte")
    parser.add_argument("email", help="le compte, par son email")
    parser.add_argument("--dry-run", action="store_true", help="simule : affiche ce que FCM recevrait, sans rien envoyer")
    args = parser.parse_args()
    sent = send_test(args.email, dry_run=args.dry_run)
    if not sent:
        sys.exit(f"{args.email} : aucun appareil n'a autorisé les notifications (Mon compte › Notifications).")
    for s in sent:
        print(f"{s.device.platform} …{s.device.token[-8:]} : {SAID[s.status]}" + (f"\n  {s.detail}" if s.status != "sent" else ""))
    if any(s.status == "error" for s in sent):
        sys.exit(1)


if __name__ == "__main__":
    main()
