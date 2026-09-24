"""Enrichment of kept activities: image, excerpt of the official site, short description.

- Image: the activity's own (Que Faire à Paris photo), else the official site's
  og:image (origin stored; licence to check before publication), else a Google
  Places photo when GOOGLE_PLACES_API_KEY is set. Google forbids caching photo
  names, so only the place id is stored; the admin fetches a fresh photo.
- Booking link: when the activity has none, the official site's "Réserver"
  link (e.g. a theatre page pointing to its ticketing).
- Description: one or two sentences written by Claude when ANTHROPIC_API_KEY is
  set, from the facts and a licensed text: the source's own (Que Faire à Paris,
  ODbL) or the official site's excerpt. Never from a curation media's text.

Only activities not enriched yet are processed, so the nightly run stays cheap.
"""

import argparse
import html
import os
import re
import unicodedata
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from surprise.categories import CATEGORIES
from surprise.collectors.common import BOOKING
from surprise.local_store import LocalStore

USER_AGENT = "surprise-collector/0.1"
PLACES_URL = "https://places.googleapis.com/v1"
# Around Notre-Dame, covering Paris intra-muros.
PARIS_CENTER = {"latitude": 48.8566, "longitude": 2.3522}
DEFAULT_MODEL = "claude-opus-5-5"
MAX_SOURCE_CHARS = 2000
MAX_DESCRIPTION_CHARS = 280

_META = re.compile(r"<meta\s[^>]*>", re.IGNORECASE)
_ATTRIBUTE = re.compile(r"([\w:-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')")
_TAG = re.compile(r"<[^>]+>")
_ANCHOR = re.compile(r"<a\s[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
# Links that look like booking but lead elsewhere.
# Any URL in the page source, including JSON of JavaScript-built sites.
_URL = re.compile(r"https?://[^\s\"'<>\\]+")
_WORD = re.compile(r"[a-z0-9]{4,}")
# A site's home page, possibly in a language ("/", "/en", "/fr-fr/").
_HOME_PAGE = re.compile(r"(?:[a-z]{2}(?:[-_][a-z]{2})?)?", re.IGNORECASE)
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
        if _is_deep_link(url) and not _NOT_BOOKING.search(f"{url} {label}"):
            anchors.append((url, label))
    labelled = [url for url, label in anchors if BOOKING.search(label)]
    ticketing = [url for url, _ in anchors if BOOKING.search(urlsplit(url).netloc)]
    if title:
        # JavaScript-built sites keep their links in JSON, not in anchors.
        in_source = [url for url in _URL.findall(page) if BOOKING.search(urlsplit(url).netloc) and _is_deep_link(url)]
        wanted = _words(title)
        best = max(labelled + ticketing + in_source, key=lambda url: len(wanted & _words(url)), default=None)
        if best and len(wanted & _words(best)) >= min(2, len(wanted)):
            return best
    return next(iter(labelled + ticketing), None)


def _is_deep_link(url: str) -> bool:
    """A page of its own: a site's home page or a same-page anchor is not the activity's booking."""
    return url.startswith("http") and bool(urlsplit(url).path.strip("/")) and "#" not in url and not _NOT_BOOKING.search(url)


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


def describe(anthropic_client: Any, model: str, activity: dict[str, Any], source_text: str | None) -> str | None:
    """Short description written by Claude from the facts and a licensed source text."""
    import anthropic

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
    except anthropic.APIStatusError as error:
        if error.status_code in (400, 404):
            raise
        return None
    except anthropic.APIConnectionError:
        return None
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
    # The official site gives the image, the booking link and, when the source has no licensed text, the excerpt to rewrite.
    website = activity.get("website")
    fetch_site = bool(website) and (not has_image or not has_booking or not item.get("source_text"))
    if fetch_site:
        preview = site_preview(http, website, activity.get("title"))
    if not has_image and preview.image_url:
        fields.update(image_url=preview.image_url, image_origin=activity["website"])
    elif not has_image and places_key:
        venue = activity.get("venue") or {}
        query = " ".join(filter(None, [venue.get("name"), venue.get("address"), venue.get("postal_code"), "Paris"]))
        try:
            fields["place_id"] = find_place(http, places_key, query)
        except httpx.HTTPError:
            pass
    # Only what was looked up: a refresh must not erase a value found before.
    if fetch_site and not has_booking:
        fields["booking_url"] = preview.booking_url
    # The home page of an event's venue describes the venue, not the event.
    about_venue = activity.get("kind") == "temporary" and website and _HOME_PAGE.fullmatch(urlsplit(website).path.strip("/"))
    excerpt = None if about_venue else preview.description
    if fetch_site:
        fields["site_excerpt"] = excerpt
    source_text = item.get("source_text") or excerpt
    if describer and source_text:
        fields["description"] = describer(activity, source_text)
    return fields


def _prompt(activity: dict[str, Any], source_text: str | None) -> str:
    venue = activity.get("venue") or {}
    categories = ", ".join(CATEGORIES[c] for c in activity.get("categories") or [])
    facts = [
        f"Titre : {activity['title']}",
        f"Lieu : {venue.get('name')} ({venue.get('arrondissement')}e arrondissement)" if venue else None,
        f"Type : {categories}" if categories else None,
        "Lieu permanent" if activity.get("kind") == "permanent" else None,
    ]
    text = re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", source_text or ""))).strip()[:MAX_SOURCE_CHARS]
    return "\n".join(filter(None, facts)) + f"\n\nTexte source (à reformuler, ne pas recopier) :\n{text}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, help="nombre maximum d'activités à traiter")
    parser.add_argument("--refresh", action="store_true", help="retraiter aussi les activités déjà enrichies")
    parser.add_argument("--no-descriptions", action="store_true", help="images et extraits seulement, sans appel à Claude")
    parser.add_argument("--source", action="append", help="ne traiter que cette source (répétable)")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    places_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    describer, model = None, None
    # Only an explicit project key: never fall back on other credentials found in the environment.
    if not args.no_descriptions and os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic

        model = os.environ.get("SURPRISE_LLM_MODEL", DEFAULT_MODEL)
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        describer = lambda activity, text: describe(client, model, activity, text)  # noqa: E731
    else:
        print("Descriptions désactivées (ANTHROPIC_API_KEY absente ou --no-descriptions)")
    if not places_key:
        print("Photos Google Places désactivées (GOOGLE_PLACES_API_KEY absente)")

    with LocalStore() as store:
        items = store.pending_enrichment(args.refresh, missing_description=describer is not None)
        items = [item for item in items if not args.source or item["source_id"] in args.source][: args.limit]
        print(f"{len(items)} activités à enrichir")
        counts: Counter[str] = Counter()
        headers = {"User-Agent": USER_AGENT}
        with httpx.Client(timeout=15, follow_redirects=True, headers=headers) as http, ThreadPoolExecutor(args.workers) as pool:
            futures = {pool.submit(enrich_one, item, http, places_key, describer): item for item in items}
            for done, future in enumerate(as_completed(futures), 1):
                item = futures[future]
                fields = future.result()
                if fields.get("description"):
                    fields["description_model"] = model
                store.save_enrichment(item["source_id"], item["external_id"], fields)
                counts.update(key for key, value in fields.items() if value)
                if done % 100 == 0:
                    print(f"  {done}/{len(items)}")
    print(
        f"images du site officiel : {counts['image_url']}, liens de réservation : {counts['booking_url']}, lieux Google : {counts['place_id']}, "
        f"extraits : {counts['site_excerpt']}, descriptions : {counts['description']}"
    )


if __name__ == "__main__":
    main()
