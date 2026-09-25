"""Online booking: is an activity really bookable, through a known ticketing or booking site?

A booking link counts when it leads to a ticketing or booking platform (Fever,
Billetweb, Zenchef…), a venue's own ticketing ("billetterie.", "tickets."
subdomains), or a venue page that embeds a booking widget (Bookeo, 4escape,
Zenchef…). A link to a venue's home page or information page does not.

Bars, clubs and restaurants need no booking: a couple can walk in while they are open.
"""

import re
from collections.abc import Iterable
from urllib.parse import urlsplit

import httpx

from surprise.models import Activity

# Platform domains and widget markers, as they appear in a link or in a page's HTML.
ENGINES = {
    "Fever": r"feverup\.com",
    "Funbooker": r"funbooker\.com",
    "Come to Paris": r"cometoparis\.com",
    "Paris je t'aime": r"ticket\.parisjetaime\.com",
    "Wecandoo": r"wecandoo\.fr/atelier/",
    "Civitatis": r"civitatis\.com/[a-z]{2}/[\w-]+/[\w-]+",
    "Explore Paris": r"exploreparis\.com/[a-z]{2}/\d+-",
    "Hati Hati": r"hati-hati\.fr/page_activite/",
    "Billetweb": r"billetweb\.fr",
    "Weezevent": r"weezevent\.com",
    "HelloAsso": r"helloasso\.com/associations/[^\"'\s]*/(?:evenements|billetteries|formulaires)",
    "Shotgun": r"shotgun\.live",
    "Dice": r"dice\.fm",
    "Eventbrite": r"eventbrite\.(?:fr|com)",
    "Ticketmaster": r"ticketmaster\.fr",
    "Fnac Spectacles": r"fnacspectacles\.com|francebillet\.com",
    "Digitick": r"digitick\.com",
    "See Tickets": r"seetickets\.com",
    "Ticketac": r"ticketac\.com",
    "BilletRéduc": r"billetreduc\.com",
    "Mapado": r"mapado\.com",
    "Tickeasy": r"tickeasy\.com",
    "Themis": r"themisweb\.fr",
    "Secutix": r"/selection/(?:timeslotpass|event)\b|secutix\.com",
    "Placeminute": r"placeminute\.com",
    "Tiqets": r"tiqets\.com",
    "GetYourGuide": r"getyourguide\.(?:fr|com)",
    "Regiondo": r"regiondo\.(?:fr|com)",
    "Bookingkit": r"bookingkit\.(?:de|net|com)",
    "FareHarbor": r"fareharbor\.com",
    "Bookeo": r"bookeo\.com/(?:widget\.js|[\w-]+)",
    "4escape": r"4escape\.(?:io|app)|class=\"forescape(?:-catalog|-cart)?\"",
    "SimplyBook": r"simplybook\.(?:it|me)",
    "Zenchef": r"bookings\.zenchef\.com|widget\.zenchef\.com|sdk\.zenchef\.com",
    "TheFork": r"thefork\.fr|lafourchette\.com",
    "SevenRooms": r"sevenrooms\.com/(?:reservations|explore)",
    "OpenTable": r"opentable\.(?:fr|com)/(?:r/|restref|booking)",
    "Guestonline": r"guestonline\.(?:io|fr)",
    "Resy": r"resy\.com/cities",
}
_ENGINE_PATTERNS = {name: re.compile(pattern, re.IGNORECASE) for name, pattern in ENGINES.items()}
# A venue's own ticketing: "billetterie.opera-comique.com", "tickets.monuments-nationaux.fr".
# Places a couple can walk into without booking.
WALK_IN_CATEGORIES = {"bar", "nuit", "restaurant"}
# The source or the official site says the place has closed for good.
CLOSED = re.compile(
    r"ferm[ée]e?s? d[ée]finitivement|d[ée]finitivement ferm[ée]|fermeture d[ée]finitive|a ferm[ée] ses portes|"
    r"permanently closed|closed permanently",
    re.IGNORECASE,
)
_TICKETING_HOST = re.compile(r"^(?:www\.)?(?:billetterie|billeterie|tickets?|booking|reservations?|resa)[.-]", re.IGNORECASE)


def engine_in(text: str) -> str | None:
    """The first known platform named in a link or a page."""
    return next((name for name, pattern in _ENGINE_PATTERNS.items() if pattern.search(text)), None)


def booking_engine(client: httpx.Client, urls: Iterable[str]) -> str | None:
    """Where the activity can be booked online: in its links first, then in the pages they lead to."""
    urls = list(dict.fromkeys(urls))
    for url in urls:
        if engine := engine_in(url):
            return engine
        if _TICKETING_HOST.search(urlsplit(url).hostname or ""):
            return "billetterie du lieu"
    # Imported here: the enrichment imports the collectors, which check bookings with this module.
    from surprise.enrich import booking_link

    for url in urls:
        page = _get(client, url)
        if page is None:
            continue
        if engine := engine_in(str(page.url)) or engine_in(page.text):
            return engine
        # The site's "Réserver" page ("perpette.com/reserver/") embeds the widget.
        if (link := booking_link(str(page.url), page.text)) and (linked := _get(client, link)):
            if engine := engine_in(str(linked.url)) or engine_in(linked.text):
                return engine
    return None


def _get(client: httpx.Client, url: str) -> httpx.Response | None:
    try:
        page = client.get(url)
    except httpx.HTTPError:
        return None
    return page if page.is_success else None


def is_free(activity: Activity) -> bool:
    return any(offer.is_free for offer in activity.offers)


def is_walk_in(activity: Activity) -> bool:
    """A bar, club or restaurant: being open is enough."""
    return bool(WALK_IN_CATEGORIES & set(activity.categories))


def is_open(client: httpx.Client, activity: Activity, source_text: str = "") -> bool:
    """Neither the source nor the official site says the place has closed for good."""
    if CLOSED.search(source_text):
        return False
    page = _get(client, str(activity.website)) if activity.website else None
    return not (page and CLOSED.search(page.text))


def booking_urls(activity: Activity) -> list[str]:
    """Booking links first, then the official site, whose "Réserver" button or widget often leads to the platform."""
    urls = [str(offer.booking_url) for offer in activity.offers if offer.booking_url]
    return urls + [str(activity.website)] if activity.website else urls
