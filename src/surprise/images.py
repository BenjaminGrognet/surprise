"""Local copies of the images that their site forbids showing elsewhere.

BilletRéduc answers "Cross-Origin-Resource-Policy: same-site": browsers refuse
its posters on any other page, though the files download fine. Those images
are copied once into data/images and served from there.
"""

import hashlib
import re
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from surprise.collectors.facts import BROWSER_HEADERS
from surprise.local_store import DEFAULT_PATH

DIRECTORY = DEFAULT_PATH.parent / "images"
# Hosts whose images carry "Cross-Origin-Resource-Policy: same-site".
SAME_SITE_HOSTS = frozenset({"www.billetreduc.com", "box.billetreduc.com"})
_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
MEDIA_TYPES = {suffix: kind for kind, suffix in _TYPES.items()}
# BilletRéduc posters are 1920 px wide (600 KB): the 800 px one is plenty for a card.
_BILLETREDUC_SIZE = re.compile(r"/zg/n\d+/")


def needs_copy(url: str | None) -> bool:
    return bool(url) and urlsplit(url).hostname in SAME_SITE_HOSTS


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
