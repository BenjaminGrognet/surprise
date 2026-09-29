"""Collector for Paris City Game (curation media of fun activities, tier 3).

The activity directory is the WordPress "project" post type, listed newest
first through the REST API. Each page has a sidebar of Divi blurbs without
heading: address, metro, website or booking link, price, phone, Instagram.
Only these facts, the title and the first gallery photo are kept.
"""

import html
import re
from typing import Any, Iterator

import httpx
from pydantic import ValidationError

from surprise.categories import categorize
from surprise.collectors.common import BOOKING, OFF_TOPIC, Normalized, euro_amounts, page, run, safe_url
from surprise.collectors.paris_zigzag import postal_code, split_venue
from surprise.models import OUT_OF_AREA, Activity, ActivityKind, Image, Offer, RawRecord, Venue

SOURCE_ID = "paris_city_game"
BASE_URL = "https://pariscitygame.fr"
PROJECTS_URL = f"{BASE_URL}/wp-json/wp/v2/project"
USER_AGENT = "surprise-collector/0.1"
DELAY_SECONDS = 1.0
PER_PAGE = 50

_BLURB = re.compile(r'<div class="et_pb_module et_pb_blurb (.*?)(?=<div class="et_pb_module |$)', re.DOTALL)
_BLURB_TEXT = re.compile(r'<div class="et_pb_blurb_description">(.*?)</div>', re.DOTALL)
_ANCHOR = re.compile(r'<a\s[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
_GALLERY_IMAGE = re.compile(r'<div class="et_pb_gallery_image[^"]*">.*?(<img[^>]*>)', re.DOTALL)
_SRC = re.compile(r'(?:data-lazy-src|src)="(https://[^"]+)"')
_NOT_OFFICIAL = re.compile(r"instagram\.com|facebook\.com|tiktok\.com|pariscitygame\.fr|cdn-cgi", re.IGNORECASE)
_CHILD_AUDIENCE = re.compile(r"jeune public|pour enfants|\benfants?\b|\bkids?\b", re.IGNORECASE)
_FREE = re.compile(r"gratuit|entrée libre", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_POSTAL_CODE = re.compile(r"\b\d{5}\b")
# The tagline under the title ("Le Karaoké nouvelle génération à Paris 12"), when there is one.
_TAGLINE = re.compile(r"<h3[^>]*>(.*?)</h3>", re.DOTALL)
# Blurbs are facts; a long one is editorial text.
MAX_FACT_CHARS = 120


def fetch_projects(client: httpx.Client) -> Iterator[dict[str, Any]]:
    """Projects newest first: id, link, title."""
    page = 1
    while True:
        response = client.get(PROJECTS_URL, params={"per_page": PER_PAGE, "page": page, "_fields": "id,slug,link,title,modified"})
        if response.status_code == 400:  # past the last page
            return
        response.raise_for_status()
        yield from response.json()
        if page >= int(response.headers.get("x-wp-totalpages", page)):
            return
        page += 1


def parse_project(project: dict[str, Any], page: str) -> dict[str, Any]:
    """Facts of a project page: the sidebar blurbs without heading, and the first gallery photo."""
    texts, links = [], []
    for blurb in _BLURB.findall(page):
        if "et_pb_module_header" in blurb:
            continue
        if text := _BLURB_TEXT.search(blurb):
            if len(fact := _text(text.group(1))) <= MAX_FACT_CHARS:
                texts.append(fact)
        links += [(html.unescape(link), _text(label)) for link, label in _ANCHOR.findall(blurb) if not _NOT_OFFICIAL.search(link)]
    tagline = _TAGLINE.search(page)
    image = _GALLERY_IMAGE.search(page)
    src = _SRC.search(image.group(1)) if image else None
    return {
        "id": project["id"],
        "url": project["link"],
        "name": _text(project["title"]["rendered"]),
        "slug": project["slug"],
        "tagline": _text(tagline.group(1)) if tagline and "description" not in tagline.group(1).lower() else None,
        "modified": project.get("modified"),
        "address": next((text for text in texts if _POSTAL_CODE.search(text)), None),
        "price": next((text for text in texts if "€" in text or _FREE.search(text)), None),
        "website": next((link for link, _ in links), None),
        # "Réserver une session": the link is labelled as the booking one, even to a home page.
        "booking_url": next((link for link, label in links if BOOKING.search(label) or BOOKING.search(link)), None),
        "image_url": src.group(1) if src else None,
    }


def to_raw_record(payload: dict[str, Any]) -> RawRecord:
    return RawRecord(source_id=SOURCE_ID, external_id=str(payload["id"]), url=safe_url(payload["url"]), payload=payload)


def normalize(payload: dict[str, Any]) -> Normalized:
    raw = to_raw_record(payload)
    name = payload["name"]
    if _CHILD_AUDIENCE.search(name):
        return Normalized(raw, rejection="jeune public")
    if OFF_TOPIC.search(name):
        return Normalized(raw, rejection="hors sujet")
    address = payload.get("address")
    if not address:
        return Normalized(raw, rejection="sans lieu")
    _, street = split_venue(address, default_name=name)
    try:
        venue = Venue(name=name, address=street, postal_code=postal_code(address) or "")
    except ValidationError:
        return Normalized(raw, rejection=OUT_OF_AREA)
    price_text = payload.get("price") or ""
    amounts = euro_amounts(price_text)
    is_free = bool(_FREE.search(price_text)) and not any(amounts)
    try:
        activity = Activity(
            title=name,
            kind=ActivityKind.PERMANENT,
            website=safe_url(payload.get("website")),
            image=Image(url=payload["image_url"], license="Paris City Game", source_url=raw.url) if payload.get("image_url") else None,
            venue=venue,
            categories=categorize(" ".join(filter(None, [name, payload["slug"].replace("-", " "), payload.get("tagline")]))),
            offers=[
                Offer(
                    label=price_text[:200] or None,
                    is_free=is_free,
                    price_min=amounts[0] if amounts and not is_free else None,
                    price_max=amounts[-1] if amounts and not is_free else None,
                    booking_url=safe_url(payload.get("booking_url")),
                    online_booking=True if payload.get("booking_url") else None,
                )
            ],
        )
    except ValidationError as error:
        return Normalized(raw, rejection=f"invalide : {error}")
    return Normalized(raw, activity=activity)


def collect(client: httpx.Client, delay: float = DELAY_SECONDS) -> Iterator[Normalized]:
    for project in fetch_projects(client):
        for payload in page(client, project["link"], lambda r: parse_project(project, r.text), delay):
            yield normalize(payload)


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", fragment))).replace("’", "'").strip()


def main() -> None:
    run(__doc__.splitlines()[0], _collect_with_client)


def _collect_with_client() -> Iterator[Normalized]:
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        yield from collect(client)


if __name__ == "__main__":
    main()
