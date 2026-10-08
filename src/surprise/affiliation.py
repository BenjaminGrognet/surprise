"""Partner links (docs/affiliation.md): an evening's "Réserver" links turned into the booking sites' affiliate links,
once the partner's id is in .env, each with the evening's page name as its sub-id — which evening led to a booking,
nothing about the couple. Without an id, or for a site without a programme, a link stays as it is.

    GETYOURGUIDE_PARTNER_ID=ABC123        GetYourGuide: ?partner_id=…&cmp=<page>
    CIVITATIS_AID=12345                   Civitatis: ?aid=…&cmp=<page>
    AWIN_PUBLISHER_ID=987654              Awin, for the sites it serves: its deep link, clickref=<page>
    AWIN_MERCHANTS=fnacspectacles.com:1234,thefork.fr:5678,tiqets.com:9012    each site's advertiser id on Awin
"""

import os
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

AWIN = "https://www.awin1.com/cread.php"


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def _on(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def _with(url: str, params: dict[str, str]) -> str:
    """The link with these parameters set, once each, its others kept in their order."""
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key not in params]
    return urlunsplit(parts._replace(query=urlencode(query + list(params.items()))))


def _merchants() -> dict[str, str]:
    """AWIN_MERCHANTS: each site's advertiser id on Awin."""
    found = {}
    for pair in os.environ.get("AWIN_MERCHANTS", "").split(","):
        domain, _, merchant = pair.strip().partition(":")
        if domain and merchant.strip():
            found[domain.strip().lower().removeprefix("www.")] = merchant.strip()
    return found


def partner(url: str | None, page: str) -> tuple[str | None, bool]:
    """The link to show for this evening (`page`, its sub-id), and whether it is a partner's."""
    if not url or not url.startswith(("http://", "https://")) or _host(url) == "awin1.com":
        return url, False
    host = _host(url)
    if (gyg := os.environ.get("GETYOURGUIDE_PARTNER_ID")) and any(_on(host, f"getyourguide.{tld}") for tld in ("com", "fr", "de", "es", "it", "co.uk")):
        return _with(url, {"partner_id": gyg, "cmp": page}), True
    if (aid := os.environ.get("CIVITATIS_AID")) and _on(host, "civitatis.com"):
        return _with(url, {"aid": aid, "cmp": page}), True
    publisher = os.environ.get("AWIN_PUBLISHER_ID")
    for domain, merchant in _merchants().items() if publisher else ():
        if _on(host, domain):
            query = urlencode({"awinmid": merchant, "awinaffid": publisher, "clickref": page})
            return f"{AWIN}?{query}&ued={quote(url, safe='')}", True
    return url, False
