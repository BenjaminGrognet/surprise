"""Collector for couple-outing selections (blog and guide articles, tier 3: discovery signal).

Articles listing date ideas in Paris (Hati Hati, Ryo, Love'n'Room, LoveCapsule,
Funbooker's blog, Petit Futé): each h2-h4 heading names an idea, the text down
to the next heading describes it (lead_text) and may give its address, its
official or booking link and a photo. An idea without address is located by its
name on OpenStreetMap. Headings that introduce or conclude the article are skipped;
a section that lists bookable activities (links to Hati Hati, Funbooker…) gives one idea per link.
"""

import html
import re
import time as clock
from datetime import datetime
from typing import Any, Iterator
from urllib.parse import urljoin, urlsplit

import httpx

from surprise.booking import engine_in
from surprise.collectors import funbooker
from surprise.collectors.common import BOOKING, Normalized, page, run, safe_url
from surprise.collectors.facts import BROWSER_HEADERS, address_in_text, complete_place, lines, normalize_facts, text, utc_now
from surprise.collectors.paris_zigzag import _clean_url, _slug, postal_code
from surprise.models import RawRecord

SOURCE_ID = "selections_couple"
# The richest first (bookable listings, addresses), as --limit reads them in this order.
ARTICLES = [
    "https://blog.funbooker.com/top-activites-couple-paris/",
    "https://www.lovecapsule.fr/activites-couple-paris/",
    "https://ryo.co/fr/articles/france/paris/activites-romantiques-couple-paris/",
    "https://www.blog.hati-hati.fr/activites-insolite-couple-paris/",
    "https://www.petitfute.com/d3-paris/actualite/m17-top-10-insolites-voyage/a30514-que-faire-a-paris-en-amoureux-top-15-des-activites.html",
    "https://lovenroom.fr/activites-en-couple-a-paris-idees-romantiques-et-insolites/",
]
DELAY_SECONDS = 1.0

_HEADING = re.compile(r"<(h[234])\b[^>]*>(.*?)</\1>", re.DOTALL | re.IGNORECASE)
_LINK = re.compile(r"<a\s[^>]*href=\"([^\"]+)\"", re.IGNORECASE)
_ANCHOR = re.compile(r"<a\s[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", re.DOTALL | re.IGNORECASE)
# Petit Futé: "Que faire à Paris en amoureux ? Une croisière sur la Seine".
_QUESTION_PREFIX = re.compile(r"^que faire à paris (?:le soir )?en amoureux\s*\?\s*", re.IGNORECASE)
_IMAGE = re.compile(r"<img\s[^>]*?(?:data-lazy-src|data-src|src)=\"(https?://[^\"]+\.(?:jpe?g|png|webp)[^\"]*)\"", re.IGNORECASE)
# "1. ", "1 — ", "#3 ", "N°2 :", emojis.
_NUMBERING = re.compile(r"^\W*(?:n°\s*)?\d{1,2}\s*[.)—–:-]?\s*|[\U0001F300-\U0001FAFF☀-➿]", re.IGNORECASE)
# Headings of the article itself, not of an idea.
_NOT_AN_IDEA = re.compile(
    r"^(?:pourquoi|comment|conseils?|faq|questions?|envie|nos |notre |trouvez|en résumé|conclusion|bonus|infos?|à propos|"
    r"sommaire|découvrez|les meilleures?|top \d|idées? |activités? (?:en couple|insolites?|romantiques?)|paris comme|"
    r"les grands classiques|expériences? sensorielles?|et si|quel|quand|où |budget|partager|articles?|commentaires?|"
    r"laisser|leave a|vous aimerez|à lire|lire aussi|newsletter|suivez|villes|guides?$|régions|services|se déplacer|"
    r"hébergement|autres articles|focus|inspiré|célébrer|sortir le soir|prêts?|paris en couple|visite du pape|"
    r"les [\w-]+ & |lovecapsule$|sorties nocturnes|décors uniques|voir )",
    re.IGNORECASE,
)
_SOCIAL = re.compile(r"facebook|instagram|twitter|pinterest|linkedin|tiktok|youtube|whatsapp|mailto:|apps\.apple|play\.google", re.IGNORECASE)


def parse_article(url: str, page: str) -> list[dict[str, Any]]:
    body_match = re.search(r"<article\b.*?</article>", page, re.DOTALL) or re.search(r"<main\b.*?</main>", page, re.DOTALL)
    body = body_match.group(0) if body_match else page
    # A template's small <article> (a card), not the post: the whole page.
    if len(_HEADING.findall(body)) < 3:
        body = page
    host = urlsplit(url).netloc.removeprefix("www.")
    headings = list(_HEADING.finditer(body))
    ideas = []
    for index, heading in enumerate(headings):
        name = _QUESTION_PREFIX.sub("", _NUMBERING.sub("", text(heading.group(2)))).strip(" :–—-.")
        section = body[heading.end() : headings[index + 1].start() if index + 1 < len(headings) else len(body)]
        section_text = lines(section) or ""
        # A section listing bookable activities ("Les Aventuriers & Gamers"): one idea per activity link.
        listed = 0
        for link, label in _ANCHOR.findall(heading.group(0) + section):
            label = text(label)
            link = _clean_url(urljoin(url, html.unescape(link)))
            if link and engine_in(link) and 10 <= len(label) <= 90 and " " in label and not BOOKING.search(label):
                name_part = label[:1].upper() + label[1:]
                ideas.append(
                    {
                        "article_url": url,
                        "name": name_part,
                        # "Paradox Museum : Défiez votre perception" is at the "Paradox Museum".
                        "venue_name": re.split(r"\s+:\s+", name_part)[0],
                        "booking_url": link,
                        "website": link,
                        "lead_text": section_text,
                    }
                )
                listed += 1
        if listed or not name or len(name) > 90 or name.endswith("?") or _NOT_AN_IDEA.search(name) or len(section_text) < 40:
            continue
        links = [_clean_url(urljoin(url, html.unescape(link))) for link in _LINK.findall(section)]
        external = [link for link in dict.fromkeys(links) if link and host not in urlsplit(link).netloc and not _SOCIAL.search(link)]
        booking = next((link for link in external if engine_in(link) or BOOKING.search(link)), None)
        image = _IMAGE.search(section)
        ideas.append(
            {
                "article_url": url,
                "name": name,
                "address": address_in_text(section_text),
                "postal_code": postal_code(section_text) if re.search(r"\bParis\s+\d{1,2}\s*(?:e|er|ème)\b|\b75\d{3}\b", section_text) else None,
                "website": next((link for link in external if link != booking), None) or booking,
                "booking_url": booking,
                "image_url": html.unescape(image.group(1)) if image else None,
                "lead_text": section_text,
            }
        )
    # An idea both named by a heading and linked in a list is kept once.
    return list({_slug(idea["name"]): idea for idea in ideas}.values())


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    article = urlsplit(payload["article_url"])
    external_id = f"{article.netloc.removeprefix('www.')}{article.path.rstrip('/')}#{_slug(payload['name'])}"
    return RawRecord(source_id=SOURCE_ID, external_id=external_id, url=safe_url(payload["article_url"]), payload=payload)


def normalize(payload: dict[str, Any], now: datetime) -> Normalized:
    return normalize_facts(to_raw_record(payload), payload, "Sélections couple", now)


def collect(client: httpx.Client, now: datetime | None = None, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    now = now or utc_now()
    for url in ARTICLES:
        for idea in page(client, url, lambda r: [complete_place(with_listing(client, i)) for i in parse_article(url, r.text)], delay):
            yield normalize(idea, now)


def with_listing(client: httpx.Client, idea: dict[str, Any]) -> dict[str, Any]:
    """An idea linked to a Funbooker listing: the listing's place, price and photo."""
    link = idea.get("booking_url") or ""
    if idea.get("address") or not funbooker._PARIS_LISTING.search(urlsplit(link).path):
        return idea
    clock.sleep(DELAY_SECONDS)
    response = client.get(link)
    if response.status_code != 200:
        return idea
    listing = funbooker.parse_listing(link, response.text)
    return idea | {
        "address": listing["address"],
        "latitude": listing["latitude"],
        "longitude": listing["longitude"],
        "price_min": listing["low_price"],
        "image_url": idea.get("image_url") or listing["image_url"],
    }


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=60, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
