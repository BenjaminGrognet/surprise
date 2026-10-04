"""Images of the activities: local copies of those their site forbids showing elsewhere, and the check that
each one shows on another site's page (`python -m surprise.images`: dead ones replaced or left out).

BilletRéduc answers "Cross-Origin-Resource-Policy: same-site": browsers refuse
its posters on any other page, though the files download fine. Sortir à Paris's
CDN answers 403 to a page of another site (it checks the Referer). Those images
are copied once into data/images and served from there.
"""

import argparse
import hashlib
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from surprise.collectors.facts import BROWSER_HEADERS
from surprise.local_store import DEFAULT_PATH, open_store

DIRECTORY = DEFAULT_PATH.parent / "images"
# Hosts whose images cannot be shown on another site: "Cross-Origin-Resource-Policy: same-site", or a Referer check.
SAME_SITE_HOSTS = frozenset({"www.billetreduc.com", "box.billetreduc.com", "cdn.sortiraparis.com"})
_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
MEDIA_TYPES = {suffix: kind for kind, suffix in _TYPES.items()}
# BilletRéduc posters are 1920 px wide (600 KB): the 800 px one is plenty for a card.
_BILLETREDUC_SIZE = re.compile(r"/zg/n\d+/")


# The checks are kept with the pages' (page_checks), under this engine; "closed": the image does not show.
CHECK = "image"
# What a browser sends for an image of another site's page: some CDNs refuse on the Referer.
_CROSS_SITE = {"Referer": "http://localhost:8081/", "Sec-Fetch-Site": "cross-site", "Sec-Fetch-Dest": "image", "Accept": "image/*"}
DELAY_SECONDS = 0.3  # between two images of one site: Time Out answers 429 to a burst


def of(item: dict[str, Any]) -> str | None:
    """The activity's image: the one found by the enrichment, else the source's."""
    return item["enrichment"].get("image_url") or (item["activity"].get("image") or {}).get("url")


def needs_copy(url: str | None) -> bool:
    return bool(url) and urlsplit(url).hostname in SAME_SITE_HOSTS


def loads(client: httpx.Client, url: str) -> bool | None:
    """Whether another site's page shows this image; None when that cannot be told now (429, timeout, copy failed)."""
    if needs_copy(url):
        return True if local_copy(url, client) else None
    try:
        with client.stream("GET", url, headers=_CROSS_SITE) as response:
            if response.status_code == 429 or response.status_code >= 500:
                return None
            kind = response.headers.get("Content-Type", "").split(";")[0].strip()
            policy = response.headers.get("Cross-Origin-Resource-Policy", "")
            return response.status_code == 200 and kind.startswith("image/") and policy not in ("same-site", "same-origin")
    except httpx.HTTPError:
        return None


def local_copy(url: str, client: httpx.Client | None = None, directory: Path = DIRECTORY) -> Path | None:
    """The image's file in the directory, downloaded if it is not there yet; None if it cannot be had."""
    stem = hashlib.sha1(url.encode()).hexdigest()[:20]
    for suffix in MEDIA_TYPES:
        if (path := directory / f"{stem}{suffix}").exists():
            return path
    try:
        if client is None:
            with httpx.Client(timeout=30, follow_redirects=True, headers=BROWSER_HEADERS) as own:
                response = own.get(_smaller(url))
        else:
            response = client.get(_smaller(url))
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    suffix = _TYPES.get(response.headers.get("Content-Type", "").split(";")[0].strip())
    if not suffix:
        return None
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{stem}{suffix}"
    path.write_bytes(response.content)
    return path


def _smaller(url: str) -> str:
    return _BILLETREDUC_SIZE.sub("/zg/n800/", url, count=1)


def replacement(client: httpx.Client, item: dict[str, Any], dead: str) -> str | None:
    """Another image for an activity whose image is dead: the official site's (og:image), if it shows."""
    from surprise.enrich import _SOCIAL, site_preview  # enrich is heavier and not needed to show an image

    activity = item["activity"]
    website = activity.get("website") or (activity.get("venue") or {}).get("website")
    if not website or _SOCIAL.search(urlsplit(website).netloc or ""):
        return None
    image = site_preview(client, website, activity.get("title")).image_url
    return image if image and image != dead and loads(client, image) else None


def check(store_url: str | None = None, refresh: bool = False, limit: int | None = None) -> None:
    """Checks the images of the activities that can be proposed; a dead one is replaced by the official site's
    (og:image), else recorded dead, which leaves the activity out of the evenings (surprise.parcours)."""
    with open_store(store_url) as store:
        items = [i for i in store.list_for_moderation() if i["status"] not in ("rejected", "filtered") and of(i)]
        known = {url for url, (engine, *_) in store.page_checks().items() if engine == CHECK} if not refresh else set()
    by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        if of(item) not in known:
            by_url[of(item)].append(item)
    urls = list(by_url)[:limit]
    by_host: dict[str, list[str]] = defaultdict(list)
    for url in urls:
        by_host[urlsplit(url).hostname or ""].append(url)
    print(f"{len(urls)} images à vérifier, sur {len(by_host)} sites")
    verdicts: dict[str, bool] = {}

    def one_site(site_urls: list[str]) -> None:
        with httpx.Client(timeout=20, follow_redirects=True, headers=BROWSER_HEADERS) as client:
            for url in site_urls:
                if (ok := loads(client, url)) is not None:
                    verdicts[url] = ok
                time.sleep(DELAY_SECONDS)

    with ThreadPoolExecutor(16) as pool:
        list(pool.map(one_site, by_host.values()))
    dead = [url for url, ok in verdicts.items() if not ok]
    replaced = 0
    with httpx.Client(timeout=20, follow_redirects=True, headers=BROWSER_HEADERS) as client, open_store(store_url) as store:
        for url in dead:
            for item in by_url[url]:
                if image := replacement(client, item, url):
                    store.save_enrichment(item["source_id"], item["external_id"], {"image_url": image, "image_origin": "site officiel"})
                    replaced += 1
        store.save_page_checks({url: (CHECK, not ok, None) for url, ok in verdicts.items()})
    unknown = len(urls) - len(verdicts)
    print(f"{len(verdicts) - len(dead)} s'affichent, {len(dead)} mortes ({replaced} fiches ont une nouvelle image du site officiel),"
          f" {unknown} sans réponse (revues au prochain passage)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Vérifie que les images des activités s'affichent ; remplace ou écarte les mortes")
    parser.add_argument("--db", help="base SQLite ou URL postgresql:// (défaut : SUPABASE_DB_URL, sinon data/surprise.db)")
    parser.add_argument("--refresh", action="store_true", help="revérifier aussi les images vérifiées il y a moins d'un mois")
    parser.add_argument("--limit", type=int, help="nombre maximum d'images à vérifier")
    args = parser.parse_args()
    sys.stdout.reconfigure(errors="replace")
    check(args.db, args.refresh, args.limit)


if __name__ == "__main__":
    main()
