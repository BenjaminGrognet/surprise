"""Emails out, through any provider's SMTP relay (Brevo, Mailjet, Resend, Gmail, OVH…): SMTP_URL names it, its account
and password, `smtps://` for TLS from the start (port 465), `smtp://` for STARTTLS (587); MAIL_FROM is who sends them.

    SMTP_URL=smtps://utilisateur:mot-de-passe@smtp-relay.brevo.com:465
    MAIL_FROM=Secret Date <bonjour@secretdate.fr>

Each email has its text and its HTML, and the link to stop them that mail clients show beside the sender (one-click,
RFC 8058) when it has one. Without SMTP_URL, nothing can be sent: the letters are only shown (dry run).
"""

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from urllib.parse import unquote, urlsplit

DEFAULT_FROM = "Secret Date <bonjour@secretdate.fr>"


@dataclass(frozen=True)
class Letter:
    to: str
    subject: str
    text: str
    html: str
    unsubscribe: str | None = None  # the link that stops them, one click


@dataclass(frozen=True)
class Relay:
    host: str
    port: int
    tls: bool  # TLS from the start (smtps), else STARTTLS
    user: str | None
    password: str | None
    sender: str


def relay(url: str | None = None, sender: str | None = None) -> Relay | None:
    """The SMTP relay of SMTP_URL (and MAIL_FROM), or None when there is none."""
    url = os.environ.get("SMTP_URL", "") if url is None else url
    if not url.strip():
        return None
    parts = urlsplit(url.strip())
    if parts.scheme not in ("smtp", "smtps") or not parts.hostname:
        raise ValueError("SMTP_URL : smtps://utilisateur:mot-de-passe@hôte:465 ou smtp://…:587")
    tls = parts.scheme == "smtps"
    return Relay(
        host=parts.hostname, port=parts.port or (465 if tls else 587), tls=tls,
        user=unquote(parts.username) if parts.username else None, password=unquote(parts.password) if parts.password else None,
        sender=sender or os.environ.get("MAIL_FROM") or DEFAULT_FROM,
    )


def message(letter: Letter, sender: str) -> EmailMessage:
    """The email as it goes: its text, its HTML beside, and how to stop them."""
    email = EmailMessage()
    email["From"] = sender
    email["To"] = letter.to
    email["Subject"] = letter.subject
    email["Date"] = formatdate(localtime=True)
    email["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[-1].strip("> ") or None)
    if letter.unsubscribe:
        email["List-Unsubscribe"] = f"<{letter.unsubscribe}>"
        email["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    email.set_content(letter.text)
    email.add_alternative(letter.html, subtype="html")
    return email


def send(letters: list[Letter], via: Relay) -> list[tuple[Letter, str]]:
    """Each letter sent through one connection: (letter, "") once sent, (letter, why) when it was refused."""
    if not letters:
        return []
    done = []
    context = ssl.create_default_context()
    connect = smtplib.SMTP_SSL(via.host, via.port, timeout=30, context=context) if via.tls else smtplib.SMTP(via.host, via.port, timeout=30)
    with connect as server:
        if not via.tls:
            server.starttls(context=context)
        if via.user:
            server.login(via.user, via.password or "")
        for letter in letters:
            try:
                server.send_message(message(letter, via.sender))
                done.append((letter, ""))
            except smtplib.SMTPException as error:  # this address refused: the others go on
                done.append((letter, f"{type(error).__name__}: {error}"))
    return done
