"""Enrichment of kept activities: image, excerpt of the official site, short description.

- Image: the activity's own (Que Faire à Paris photo), else the official site's
  og:image (its origin stored), else a Google Places photo when
  GOOGLE_PLACES_API_KEY is set. Google forbids caching photo names, so only the
  place id is stored; the admin fetches a fresh photo.
- Booking link: when the activity has none, the official site's "Réserver"
  link (e.g. a theatre page pointing to its ticketing).
- Place: coordinates, opening hours and, when missing, the address from
  OpenStreetMap (open data): the named places of Paris downloaded once from
  Overpass, matched by name and postcode or distance, else Nominatim. Each
  venue's answer is stored, so it is asked once. An event with coordinates skips
  it: a venue's opening hours say nothing of an event's dates.
- Description: the first sentences, up to 280 characters, of the source's own
  text (Que Faire à Paris, a media's article) or else of the official site's
  excerpt, cleaned of markup, page titles and lists; no outside call. With
  --claude, written by Claude instead (ANTHROPIC_API_KEY) from the facts and
  that text.
  An activity already enriched only gets its description: nothing is fetched.

Only activities not enriched yet are processed, so the nightly run stays cheap.
"""

import argparse
import functools
import html
import json
import math
import os
import re
import threading
import time
import unicodedata
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from surprise.categories import CATEGORIES
from surprise.collectors.common import BOOKING
from surprise.local_store import open_store

USER_AGENT = "surprise-collector/0.1"
PLACES_URL = "https://places.googleapis.com/v1"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy: at most one request per second.
NOMINATIM_DELAY = 1.0
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Every named place of Paris and its inner suburbs (90 000, 34 MB, about 10 s), downloaded again after a week.
OVERPASS_QUERY = (
    '[out:json][timeout:180];nwr["name"][~"^(amenity|leisure|tourism|shop|club|craft|sport|historic)$"~"."]'
    "(48.80,2.20,48.93,2.48);out center tags;"
)
OVERPASS_FILE = Path("data/osm_paris.json")
OVERPASS_DAYS = 7
# A venue given with coordinates is the OSM place of its name this close.
NEAR_METRES = 300
# Around Notre-Dame, covering Paris intra-muros.
PARIS_CENTER = {"latitude": 48.8566, "longitude": 2.3522}
DEFAULT_MODEL = "claude-opus-5-5"
MAX_SOURCE_CHARS = 2000
MAX_DESCRIPTION_CHARS = 280

_META = re.compile(r"<meta\s[^>]*>", re.IGNORECASE)
_ATTRIBUTE = re.compile(r"(?<![\w:-])([\w:-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')")
_TAG = re.compile(r"<[^>]+>")
_ANCHOR = re.compile(r"<a\s[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
# Links that look like booking but lead elsewhere.
_WORDPRESS_PAGE = re.compile(r"^(?:p|page_id|event)=\d+$")
# Any URL in the page source, including JSON of JavaScript-built sites.
# No brackets: "https://[domain]/…" in a page's script is no link, and urlsplit refuses it.
_URL = re.compile(r"https?://[^\s\"'<>\\\[\]]+")
_WORD = re.compile(r"[a-z0-9]{4,}")
# A site's home page, possibly in a language ("/", "/en", "/fr-fr/").
_HOME_PAGE = re.compile(r"(?:[a-z]{2}(?:[-_][a-z]{2})?)?", re.IGNORECASE)
# Social profiles: their og tags describe the account (followers, posts), not the place.
_SOCIAL = re.compile(r"(?:^|\.)(?:instagram\.com|facebook\.com|tiktok\.com|linktr\.ee|x\.com|twitter\.com)$", re.IGNORECASE)
_BUY = re.compile(r"^\s*(?:achet(?:er|ez)|r[ée]serv(?:er|ez)|buy|book)\b", re.IGNORECASE)
_NOT_BOOKING = re.compile(r"cadeau|gift|newsletter|groupe|en-nombre|professionnel|entreprise|privatis|mentions|cgv|conditions", re.IGNORECASE)

SYSTEM_PROMPT = """Tu rédiges les fiches d'un site qui propose des sorties originales en couple à Paris.
Pour chaque activité, écris une description courte en français : une ou deux phrases, 280 caractères maximum.
- Reformule avec tes propres mots : ne recopie aucune phrase ni tournure du texte source.
- N'invente rien : pas de date, prix, horaire ou détail absent des informations fournies.
- Ton sobre et donnant envie, sans superlatifs creux ni point d'exclamation.
- Réponds uniquement par la description, sans guillemets ni titre."""


@dataclass
class SitePreview:
    image_url: str | None = None
    description: str | None = None
    booking_url: str | None = None


def site_preview(client: httpx.Client, url: str, title: str | None = None) -> SitePreview:
    """og:image and description of a page; empty when the site does not answer."""
    try:
        response = client.get(url)
    except httpx.HTTPError:
        return SitePreview()
    if response.status_code != 200 or "html" not in response.headers.get("content-type", ""):
        return SitePreview()
    meta: dict[str, str] = {}
    for tag in _META.findall(response.text[:300_000]):
        attributes = {k.lower(): html.unescape(a or b) for k, a, b in _ATTRIBUTE.findall(tag)}
        key = attributes.get("property") or attributes.get("name")
        if key and "content" in attributes:
            meta.setdefault(key.lower(), attributes["content"].strip())
    image = meta.get("og:image") or meta.get("og:image:url") or meta.get("twitter:image")
    description = meta.get("og:description") or meta.get("description") or meta.get("twitter:description")
    return SitePreview(
        image_url=urljoin(str(response.url), image) if image else None,
        description=description or None,
        booking_url=booking_link(str(response.url), response.text, title),
    )


def booking_link(page_url: str, page: str, title: str | None = None) -> str | None:
    """The page's booking link.

    A page listing several shows (a theatre's programme) links to each one's
    ticketing: the link naming the activity wins ("billetweb.fr/adjani-les-murmures-de-l-ame"
    for "Isabelle Adjani, Les murmures de l'âme"). Otherwise a "Réserver" /
    "Billetterie" anchor, else an anchor to a ticketing site.
    """
    anchors = []
    for href, text in _ANCHOR.findall(page):
        url = urljoin(page_url, html.unescape(href).strip())
        label = _TAG.sub("", html.unescape(text)).strip()
        if _is_deep_link(url) and not _NOT_BOOKING.search(f"{url} {label}") and not _is_sibling(page_url, url):
            anchors.append((url, label))
    # A buying button ("Acheter", "Réserver") before a menu entry ("Billetterie", the whole programme).
    labelled = [url for url, label in anchors if _BUY.search(label)] + [url for url, label in anchors if BOOKING.search(label)]
    ticketing = [url for url, _ in anchors if BOOKING.search(urlsplit(url).netloc)]
    if title:
        # JavaScript-built sites keep their links in JSON, not in anchors.
        in_source = [url for url in _URL.findall(page) if BOOKING.search(urlsplit(url).netloc) and _is_deep_link(url)]
        wanted = _words(title)
        best = max(labelled + ticketing + in_source, key=lambda url: len(wanted & _words(url)), default=None)
        if best and len(wanted & _words(best)) >= min(2, len(wanted)):
            return best
    return next(iter(labelled + ticketing), None)


def _is_sibling(page_url: str, url: str) -> bool:
    """Another page of the same listing ("paris.fr/evenements/a" → "/evenements/b"): another event, not this one's booking."""
    page, link = urlsplit(page_url), urlsplit(url)
    parent = page.path.rstrip("/").rpartition("/")[0]
    return bool(parent) and page.netloc == link.netloc and link.path.rstrip("/").rpartition("/")[0] == parent and link.path != page.path


def _is_deep_link(url: str) -> bool:
    """A page of its own: a site's home page or a same-page anchor is not the activity's booking.

    A WordPress page may be given by its number ("lemelville.fr/?p=6098").
    """
    parts = urlsplit(url)
    own_page = bool(parts.path.strip("/")) or bool(_WORDPRESS_PAGE.match(parts.query))
    return url.startswith("http") and own_page and "#" not in url and not _NOT_BOOKING.search(url)


def _words(text: str) -> set[str]:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return set(_WORD.findall(ascii_text)) - {"paris", "https", "html", "event", "events", "www"}


def find_place(client: httpx.Client, api_key: str, query: str) -> str | None:
    """Id of the first Google place matching the query that has photos."""
    response = client.post(
        f"{PLACES_URL}/places:searchText",
        headers={"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "places.id,places.photos"},
        json={
            "textQuery": query,
            "languageCode": "fr",
            "maxResultCount": 3,
            "locationBias": {"circle": {"center": PARIS_CENTER, "radius": 12000.0}},
        },
    )
    response.raise_for_status()
    return next((p["id"] for p in response.json().get("places", []) if p.get("photos")), None)


def place_photo(client: httpx.Client, api_key: str, place_id: str, max_width: int = 800) -> dict[str, str] | None:
    """A fresh photo URL of a place, with the author attribution Google requires to display."""
    details = client.get(
        f"{PLACES_URL}/places/{place_id}", headers={"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "photos"}
    )
    details.raise_for_status()
    photos = details.json().get("photos") or []
    if not photos:
        return None
    media = client.get(
        f"{PLACES_URL}/{photos[0]['name']}/media",
        params={"maxWidthPx": max_width, "skipHttpRedirect": "true"},
        headers={"X-Goog-Api-Key": api_key},
    )
    media.raise_for_status()
    authors = [a.get("displayName") for a in photos[0].get("authorAttributions") or [] if a.get("displayName")]
    return {"photo_uri": media.json()["photoUri"], "attribution": ", ".join(authors)}


_nominatim_lock = threading.Lock()
_nominatim_next = 0.0
# OSM results that are areas or roads, not the place itself.
_PARIS_POSTCODE = re.compile(r"75\d{3}")
_NOT_A_PLACE = {"highway", "place", "boundary", "landuse", "railway"}


class _Unanswered(Exception):
    """Nominatim failed: nothing to keep, the question is asked again next time."""


def _nominatim(client: httpx.Client, url: str, params: dict[str, Any]) -> Any:
    """Nominatim's JSON answer (_Unanswered when it fails); one request per second across workers (its usage policy)."""
    global _nominatim_next
    # The lock only books the next slot: the request runs outside it, so its own duration adds no wait.
    with _nominatim_lock:
        time.sleep(max(0.0, _nominatim_next - time.monotonic()))
        _nominatim_next = time.monotonic() + NOMINATIM_DELAY
    try:
        response = client.get(url, params=params)
    except httpx.HTTPError as error:
        raise _Unanswered from error
    if response.status_code != 200:
        raise _Unanswered(response.status_code)
    return response.json()


# Each question's answer, kept in the store too (load_answers, save_answers): an address is asked once, not again at
# each collection or renormalization, at one request per second; the 46 concerts of a club ask for it once.
_answers: dict[str, Any] = {}
_new_answers: dict[str, Any] = {}
_answers_lock = threading.Lock()


def _kept(ask: Callable[..., Any]) -> Callable[..., Any]:
    """`ask` answered once per question (its arguments but the client); None when Nominatim fails, not kept."""

    @functools.wraps(ask)
    def kept(client: httpx.Client, *question: Any) -> Any:
        key = json.dumps([ask.__name__, *question], ensure_ascii=False)
        if key not in _answers:
            try:
                answer = ask(client, *question)
            except _Unanswered:
                return None
            with _answers_lock:
                _answers[key] = _new_answers[key] = answer
        return _answers[key]

    return kept


def load_answers(store: Any) -> None:
    """Nominatim's answers kept in the store: not asked again."""
    _answers.update(store.nominatim_answers())


def save_answers(store: Any) -> None:
    """Saves Nominatim's new answers, while other threads go on asking."""
    global _new_answers
    with _answers_lock:
        new, _new_answers = _new_answers, {}
    store.save_nominatim_answers(new)


@_kept
def osm_place(client: httpx.Client, name: str, address: str | None, postal_code: str | None) -> dict[str, Any] | None:
    """The OpenStreetMap place of this name in this postcode (else anywhere in Paris): coordinates, hours, address, OSM link."""
    queries = [f"{name}, {postal_code} Paris", f"{name}, {address or ''}, {postal_code} Paris"] if postal_code else [f"{name}, Paris"]
    for query in dict.fromkeys(queries):
        results = _nominatim(
            client, NOMINATIM_URL,
            {"q": query, "format": "jsonv2", "addressdetails": 1, "extratags": 1, "limit": 5, "countrycodes": "fr"},
        )
        for result in results:
            details = result.get("address") or {}
            in_place = details.get("postcode") == postal_code if postal_code else _PARIS_POSTCODE.fullmatch(details.get("postcode") or "")
            if result.get("category") in _NOT_A_PLACE or not in_place or not result.get("name"):
                continue
            street = " ".join(filter(None, [details.get("house_number"), details.get("road")]))
            return {
                "latitude": float(result["lat"]),
                "longitude": float(result["lon"]),
                "opening_hours": (result.get("extratags") or {}).get("opening_hours"),
                "osm_address": street or None,
                "osm_postal_code": details.get("postcode"),
                "osm_url": f"https://www.openstreetmap.org/{result['osm_type']}/{result['osm_id']}",
            }
    return None


@_kept
def osm_area(client: httpx.Client, query: str) -> dict[str, Any] | None:
    """Where a named spot of Paris is (a métro station, a square): its postcode and coordinates."""
    results = _nominatim(
        client, NOMINATIM_URL, {"q": f"{query}, Paris", "format": "jsonv2", "addressdetails": 1, "limit": 5, "countrycodes": "fr"}
    )
    for result in results:
        postcode = (result.get("address") or {}).get("postcode") or ""
        if _PARIS_POSTCODE.fullmatch(postcode):
            return {
                "latitude": float(result["lat"]),
                "longitude": float(result["lon"]),
                "osm_postal_code": postcode,
                "osm_url": f"https://www.openstreetmap.org/{result['osm_type']}/{result['osm_id']}",
            }
    return None


@_kept
def osm_address(client: httpx.Client, latitude: float, longitude: float) -> dict[str, Any] | None:
    """The street address and postcode at these coordinates, on OpenStreetMap."""
    result = _nominatim(
        client, NOMINATIM_URL.replace("/search", "/reverse"),
        {"lat": latitude, "lon": longitude, "format": "jsonv2", "addressdetails": 1, "zoom": 18},
    )
    details = result.get("address") or {}
    if not details.get("postcode"):
        return None
    street = " ".join(filter(None, [details.get("house_number"), details.get("road") or details.get("pedestrian")]))
    return {
        "osm_address": street or None,
        "osm_postal_code": details["postcode"],
        "osm_url": f"https://www.openstreetmap.org/{result['osm_type']}/{result['osm_id']}" if result.get("osm_type") else None,
    }


def paris_places(client: httpx.Client) -> dict[str, list[dict[str, Any]]]:
    """The named OSM places of Paris by name (see _name_key); empty when Overpass fails and no copy was kept."""
    fresh = OVERPASS_FILE.exists() and time.time() - OVERPASS_FILE.stat().st_mtime < OVERPASS_DAYS * 86400
    if not fresh:
        try:
            response = client.post(OVERPASS_URL, data={"data": OVERPASS_QUERY}, timeout=300)
            response.raise_for_status()
            OVERPASS_FILE.parent.mkdir(parents=True, exist_ok=True)
            OVERPASS_FILE.write_bytes(response.content)
        except httpx.HTTPError as error:
            print(f"Overpass indisponible ({error!r}) : copie précédente ou Nominatim seul")
    if not OVERPASS_FILE.exists():
        return {}
    index: dict[str, list[dict[str, Any]]] = {}
    for element in json.loads(OVERPASS_FILE.read_bytes())["elements"]:
        tags, point = element["tags"], element.get("center") or element
        if "lat" not in point:
            continue
        street = " ".join(filter(None, [tags.get("addr:housenumber"), tags.get("addr:street")]))
        index.setdefault(_name_key(tags["name"]), []).append({
            "latitude": point["lat"],
            "longitude": point["lon"],
            "opening_hours": tags.get("opening_hours"),
            "osm_address": street or None,
            "osm_postal_code": tags.get("addr:postcode"),
            "osm_url": f"https://www.openstreetmap.org/{element['type']}/{element['id']}",
        })
    return index


def _name_key(name: str) -> str:
    """ "Le Dipsy" and "Dipsy !" alike: no accent, case, punctuation or leading article."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"^(?:le|la|les|l) ", "", " ".join(re.findall(r"[a-z0-9]+", ascii_name)))


def match_place(index: dict[str, list[dict[str, Any]]], venue: dict[str, Any]) -> dict[str, Any] | None:
    """The OSM place of the venue's name: nearest to its coordinates, else in its postcode, else the only one of that name.

    Most OSM places carry no postcode: an untagged one is taken only when nothing contradicts it.
    """
    postcode = venue["postal_code"]
    same_name = index.get(_name_key(venue["name"]), [])
    candidates = [c for c in same_name if c["osm_postal_code"] in (None, postcode)]
    if venue.get("latitude") and venue.get("longitude"):
        near = [(_metres(c, venue), c) for c in candidates]
        place = min((pair for pair in near if pair[0] < NEAR_METRES), key=lambda pair: pair[0], default=(0, None))[1]
    else:
        tagged = [c for c in candidates if c["osm_postal_code"] == postcode]
        # ponytail: a unique untagged name may sit in a suburb of the box, not in the venue's postcode; rare enough.
        place = tagged[0] if tagged else candidates[0] if len(same_name) == 1 and candidates else None
    return place and place | {"osm_postal_code": place["osm_postal_code"] or postcode}


def _metres(place: dict[str, Any], venue: dict[str, Any]) -> float:
    dy = (place["latitude"] - venue["latitude"]) * 111_000
    dx = (place["longitude"] - venue["longitude"]) * 111_000 * math.cos(math.radians(venue["latitude"]))
    return math.hypot(dx, dy)


# Filled by main: the Overpass index, and every venue's answer (None: not found) from the store and this run.
_paris: dict[str, list[dict[str, Any]]] = {}
_places: dict[tuple[str, str], dict[str, Any] | None] = {}
_new_places: dict[tuple[str, str], dict[str, Any] | None] = {}


def venue_place(client: httpx.Client, venue: dict[str, Any]) -> dict[str, Any] | None:
    key = (venue["name"], venue["postal_code"])
    if key not in _places:
        place = match_place(_paris, venue) or osm_place(client, venue["name"], venue.get("address"), venue["postal_code"])
        _places[key] = _new_places[key] = place
    return _places[key]


# A sentence ends before a capital, a quote or a digit ("Quand … 80. Plusieurs"); a line break starting with a capital too.
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+(?=[A-ZÀ-ÝŒ«\"0-9])|(?<=[!?])(?=[A-ZÀ-Ý])|\s*\n\s*(?=[A-ZÀ-ÝŒ«\"0-9*-])")
# Time Out's first line is its page title: "La Terra Madre | Restaurants à Ménilmontant, Paris".
_PAGE_TITLE = re.compile(r"^[^\n]* \| [^\n]*(?:\n|$)")
# Paragraphs, line breaks, headings and list items end a line; other tags sit inside a sentence.
_BLOCK_END = re.compile(r"<br\s*/?>|</(?:p|div|h\d|li)>", re.IGNORECASE)
# Facts laid out as "Artiste: … Auteurs: … Durée: 60 mn", a rating, a price tag: no sentence to read.
_NOT_PROSE = re.compile(r"(?:\w\s?:.*){2}|\d(?:[,.]\d)?\s*-\s*\d+\s*avis|\bdès \d+\s*€", re.IGNORECASE)
_CUT = "…"


def summarize(text: str | None) -> str | None:
    """The text's first sentences, at most MAX_DESCRIPTION_CHARS; a single longer one cut at a word, with an ellipsis."""
    text = _BLOCK_END.sub("\n", _PAGE_TITLE.sub("", (text or "").replace("\r", "")))
    text = html.unescape(_TAG.sub(" ", text)).strip()
    # Emojis and decorations ("⭐", "***Les dimanches***") are no words.
    text = "".join(ch for ch in text if unicodedata.category(ch) != "So" and ch != "️").replace("*", "")
    sentences = []
    for sentence in _SENTENCE_END.split(text):
        sentence = re.sub(r"\s+", " ", sentence).strip(" -•")
        # A list follows ("Les bienfaits :"), or the source cut its own text ("un no..."): stop there.
        if sentence.endswith((":", "...", "…")):
            if not sentences and not sentence.endswith(":"):
                sentences.append(sentence.rstrip(".… ") + _CUT)
            break
        # A headline said again in the text ("Apprenez à réussir vos semis avec Marguerite !"): its words are mostly known.
        seen = set().union(*map(_words, sentences))
        if len(sentence) >= 15 and not _NOT_PROSE.search(sentence) and len(_words(sentence) - seen) > len(_words(sentence)) / 2:
            # A heading or a line without its full stop: "Les dimanches du Supersonic. Tous les dimanches…".
            sentences.append(sentence if sentence[-1] in ".!?…»\")" else f"{sentence}.")
    summary = ""
    for sentence in sentences:
        if summary and len(summary) + 1 + len(sentence) > MAX_DESCRIPTION_CHARS:
            break
        summary = f"{summary} {sentence}".strip()
    if len(summary) > MAX_DESCRIPTION_CHARS:
        summary = summary[: MAX_DESCRIPTION_CHARS - 1].rsplit(" ", 1)[0].rstrip(",;:.- ") + _CUT
    return summary or None


def describe_only(item: dict[str, Any], describer: Callable[[dict[str, Any], str | None], str | None]) -> dict[str, str | None]:
    """The description of an activity already enriched, from its source text or the official site's excerpt kept then."""
    text = item.get("source_text") or item.get("site_excerpt")
    return {"description": describer(item["activity"], text) if text else None}


def describe(anthropic_client: Any, model: str, activity: dict[str, Any], source_text: str | None) -> str | None:
    """Short description written by Claude from the facts and the source's text."""
    try:
        response = anthropic_client.beta.messages.create(
            model=model,
            max_tokens=2000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _prompt(activity, source_text)}],
        )
    except Exception as error:
        import anthropic  # for its errors only: the SDK takes seconds to load, the client given is already there

        if isinstance(error, anthropic.APIConnectionError) or (isinstance(error, anthropic.APIStatusError) and error.status_code not in (400, 404)):
            return None
        raise
    if response.stop_reason != "end_turn":
        return None
    text = " ".join(block.text for block in response.content if block.type == "text").strip().strip('"«» ')
    return text[:MAX_DESCRIPTION_CHARS] or None


def enrich_one(
    item: dict[str, Any],
    http: httpx.Client,
    places_key: str | None = None,
    describer: Callable[[dict[str, Any], str | None], str | None] | None = None,
) -> dict[str, str | None]:
    activity = item["activity"]
    fields: dict[str, str | None] = {}
    preview = SitePreview()
    has_image = bool(activity.get("image"))
    has_booking = any(offer.get("booking_url") for offer in activity.get("offers") or [])
    # The official site gives the image, the booking link and, when the source has no text, the excerpt to rewrite.
    website = activity.get("website")
    if website and _SOCIAL.search(urlsplit(website).netloc):
        website = None
    fetch_site = bool(website) and (not has_image or not has_booking or not item.get("source_text"))
    if fetch_site:
        preview = site_preview(http, website, activity.get("title"))
    if not has_image and preview.image_url:
        fields.update(image_url=preview.image_url, image_origin=website)
    elif not has_image and places_key:
        venue = activity.get("venue") or {}
        query = " ".join(filter(None, [venue.get("name"), venue.get("address"), venue.get("postal_code"), "Paris"]))
        try:
            fields["place_id"] = find_place(http, places_key, query)
        except httpx.HTTPError:
            pass
    venue = activity.get("venue") or {}
    # Coordinates when missing, and a permanent place's opening hours: an event keeps its own dates.
    if venue and (not venue.get("latitude") or (activity.get("kind") == "permanent" and not venue.get("opening_hours"))):
        place = venue_place(http, venue)
        if place:
            fields.update(place)
    # Only what was looked up: a refresh must not erase a value found before.
    if fetch_site and not has_booking:
        fields["booking_url"] = preview.booking_url
    # A booking link to the show's page on the venue's site: its "Acheter" button leads to the ticketing.
    show_page = next(
        (o["booking_url"] for o in activity.get("offers") or [] if o.get("booking_url") and not BOOKING.search(o["booking_url"])), None
    )
    if show_page and (ticketing := site_preview(http, show_page, activity.get("title")).booking_url):
        # Only a ticketing site: another page of the same site is often a generic "book a visit".
        if BOOKING.search(urlsplit(ticketing).netloc):
            fields["booking_url"] = ticketing
    # The home page of an event's venue describes the venue, not the event.
    about_venue = activity.get("kind") == "temporary" and website and _HOME_PAGE.fullmatch(urlsplit(website).path.strip("/"))
    excerpt = None if about_venue else preview.description
    if fetch_site:
        fields["site_excerpt"] = excerpt
    source_text = item.get("source_text") or excerpt
    if describer and source_text:
        fields["description"] = describer(activity, source_text)
    return fields


def _where(venue: dict[str, Any]) -> str:
    return f"{venue['arrondissement']}e arrondissement" if venue.get("arrondissement") else venue.get("town") or "Paris"


def _prompt(activity: dict[str, Any], source_text: str | None) -> str:
    venue = activity.get("venue") or {}
    categories = ", ".join(CATEGORIES[c] for c in activity.get("categories") or [])
    facts = [
        f"Titre : {activity['title']}",
        f"Lieu : {venue.get('name')} ({_where(venue)})" if venue else None,
        f"Type : {categories}" if categories else None,
        "Lieu permanent" if activity.get("kind") == "permanent" else None,
    ]
    text = re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", source_text or ""))).strip()[:MAX_SOURCE_CHARS]
    return "\n".join(filter(None, facts)) + f"\n\nTexte source (à reformuler, ne pas recopier) :\n{text}"


def _drain(places: dict[tuple[str, str], Any]) -> dict[tuple[str, str], Any]:
    # pop, not copy then clear: workers keep adding while the main thread saves.
    return {key: places.pop(key) for key in list(places)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, help="nombre maximum d'activités à traiter")
    parser.add_argument("--refresh", action="store_true", help="retraiter aussi les activités déjà enrichies")
    parser.add_argument("--no-descriptions", action="store_true", help="images et extraits seulement, sans description")
    parser.add_argument("--claude", action="store_true", help="descriptions rédigées par Claude (ANTHROPIC_API_KEY) au lieu d'extraites")
    parser.add_argument("--source", action="append", help="ne traiter que cette source (répétable)")
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    places_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    # By default the description is taken from the texts: no outside call. "extrait" marks it, to write it again later.
    describer, model = (lambda activity, text: summarize(text)), "extrait"
    if args.no_descriptions:
        describer, model = None, None
    # Only an explicit project key: never fall back on other credentials found in the environment.
    elif args.claude:
        import anthropic

        model = os.environ.get("SURPRISE_LLM_MODEL", DEFAULT_MODEL)
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        describer = lambda activity, text: describe(client, model, activity, text)  # noqa: E731
    if not places_key:
        print("Photos Google Places désactivées (GOOGLE_PLACES_API_KEY absente)")

    with open_store() as store:
        _places.update(store.osm_places())
        load_answers(store)
        items = store.pending_enrichment(args.refresh, missing_description=describer is not None)
        items = [item for item in items if not args.source or item["source_id"] in args.source][: args.limit]
        print(f"{len(items)} activités à enrichir")
        counts: Counter[str] = Counter()
        headers = {"User-Agent": USER_AGENT}
        with httpx.Client(timeout=15, follow_redirects=True, headers=headers) as http, ThreadPoolExecutor(args.workers) as pool:
            _paris.update(paris_places(http))
            futures = {
                pool.submit(describe_only, item, describer)
                if item["enriched"] and not args.refresh
                else pool.submit(enrich_one, item, http, places_key, describer): item
                for item in items
            }
            for done, future in enumerate(as_completed(futures), 1):
                item = futures[future]
                # One activity failing must not stop the saves of the others (the pool would still run them all).
                try:
                    fields = future.result()
                except Exception as error:  # noqa: BLE001
                    counts["erreurs"] += 1
                    print(f"  échec {item['source_id']}/{item['external_id']} : {error!r}", flush=True)
                    continue
                if fields.get("description"):
                    fields["description_model"] = model
                store.save_enrichment(item["source_id"], item["external_id"], fields)
                counts.update(key for key, value in fields.items() if value)
                if done % 100 == 0:
                    store.save_osm_places(_drain(_new_places))
                    save_answers(store)
                    print(f"  {done}/{len(items)}", flush=True)
        store.save_osm_places(_drain(_new_places))
        save_answers(store)
    print(
        f"images du site officiel : {counts['image_url']}, liens de réservation : {counts['booking_url']}, lieux Google : {counts['place_id']}, "
        f"extraits : {counts['site_excerpt']}, lieux OpenStreetMap : {counts['osm_url']}, horaires : {counts['opening_hours']}, "
        f"descriptions : {counts['description']}, erreurs : {counts['erreurs']}"
    )


if __name__ == "__main__":
    main()
