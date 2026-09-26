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
    "Notre Billetterie": r"[\w-]+\.notre-billetterie\.com",
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
    "Qweekle": r"[\w-]+\.qweekle\.com",
    # WordPress "Event Tickets": the venue sells its seats on the event's page ("Le Son de la Terre").
    "Event Tickets": r"id=\"tribe-tickets__tickets-form\"",
    "SimplyBook": r"simplybook\.(?:it|me)",
    "Zenchef": r"bookings\.zenchef\.com|widget\.zenchef\.com|sdk\.zenchef\.com",
    "TheFork": r"thefork\.fr|lafourchette\.com",
    "SevenRooms": r"sevenrooms\.com/(?:reservations|explore)",
    "OpenTable": r"opentable\.(?:fr|com)/(?:r/|restref|booking)",
    "Guestonline": r"guestonline\.(?:io|fr)",
    "Resy": r"resy\.com/cities",
    # Hotel booking engines, on the hotel's site or its "Réserver" page.
    "D-EDGE": r"secure-hotel-booking\.com|availpro\.com|fastbooking\.(?:com|net)|d-edge\.com/booking",
    "SynXis": r"synxis\.com",
    "Mews": r"app\.mews\.(?:com|li)|mews\.li/distributor",
    "Reservit": r"reservit\.com",
    "Cloudbeds": r"hotels\.cloudbeds\.com",
    "SiteMinder": r"thebookingbutton\.com|direct-book\.com|book-directonline\.com",
    "Amenitiz": r"amenitiz\.io|amenitiz\.com/booking",
    "Lighthouse": r"bookingengine\.mylighthouse\.com",
    "Profitroom": r"booking\.profitroom\.com",
    "TravelClick": r"reservations\.travelclick\.com|ihotelier\.com",
    "Accor": r"all\.accor\.com",
    "Hyatt": r"hyatt\.com/shop",
    "Marriott": r"marriott\.com/reservation",
    "Hilton": r"hilton\.com/[a-z]{2}/book",
    "WebHotelier": r"webhotelier\.net",
    "Hotelrunner": r"hotelrunner\.com",
    "Misterbooking": r"misterbooking\.(?:com|net)",
    "Booking.com": r"booking\.com/hotel/",
    "Loveroomers": r"booking\.loveroomers\.fr",
    "Love'nSpa": r"lovenspa\.fr/products/",
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
# Or one of its pages: "musee-jacquemart-andre.com/fr/tickets/6a280a…", a show's page in the site's ticketing.
_TICKETING_PATH = re.compile(r"/(?:billetterie|billeterie|tickets?|ticketing|e-?billets?)/[\w-]{3,}", re.IGNORECASE)
# An organiser's booking form ("Réservation préalable sur notre site" → a Google form): booked online too.
_FORM = re.compile(
    r"forms\.gle/|docs\.google\.com/forms/|tally\.so/r/|[\w-]+\.typeform\.com/to/|form\.jotform\.com/|framaforms\.org/",
    re.IGNORECASE,
)
_ASKS_BOOKING = re.compile(r"r[ée]serv|inscri", re.IGNORECASE)
_HOST = re.compile(r"https?://([a-z0-9.-]+)", re.IGNORECASE)


def engine_in(text: str) -> str | None:
    """The first known platform named in a link or a page."""
    return next((name for name, pattern in _ENGINE_PATTERNS.items() if pattern.search(text)), None)


def own_ticketing(url: str) -> str | None:
    """A venue's own ticketing or booking site: "billetterie.opera-comique.com", "booking.revo-partybox.com"."""
    parts = urlsplit(url)
    return "billetterie du lieu" if _TICKETING_HOST.search(parts.hostname or "") or _TICKETING_PATH.search(parts.path) else None


def ticketing_of_site(url: str, page: str) -> str | None:
    """The page links to its own site's ticketing ("38riv.com" → "billetterie.38riv.com"): the venue sells its seats."""
    domain = ".".join((urlsplit(url).hostname or "").split(".")[-2:])
    hosts = {host.lower() for host in _HOST.findall(page)}
    return "billetterie du lieu" if domain and any(_TICKETING_HOST.search(h) and h.endswith(f".{domain}") for h in hosts) else None


def booking_form(url: str, page: str) -> str | None:
    """A booking form the page links to, on a page that asks to book or register; not a survey or a newsletter."""
    return "formulaire de réservation" if (_FORM.search(url) or _FORM.search(page)) and _ASKS_BOOKING.search(page) else None


def booking_engine(client: httpx.Client, urls: Iterable[str]) -> str | None:
    """Where the activity can be booked online: in its links first, then in the pages they lead to."""
    urls = list(dict.fromkeys(urls))
    for url in urls:
        if engine := engine_in(url) or own_ticketing(url):
            return engine
    # Imported here: the enrichment imports the collectors, which check bookings with this module.
    from surprise.enrich import booking_link

    for url in urls:
        page = _get(client, url)
        if page is None:
            continue
        if engine := engine_in(str(page.url)) or engine_in(page.text) or booking_form(str(page.url), page.text):
            return engine
        if engine := ticketing_of_site(str(page.url), page.text):
            return engine
        # The site's "Réserver" page ("perpette.com/reserver/") embeds the widget.
        link = booking_link(str(page.url), page.text)
        if link and (engine := own_ticketing(link)):
            return engine
        if link and (linked := _get(client, link)):
            if engine := engine_in(str(linked.url)) or engine_in(linked.text) or ticketing_of_site(str(linked.url), linked.text):
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
    """A bar, club or restaurant: being open is enough. Not a hotel's bar: the room is booked."""
    return bool(WALK_IN_CATEGORIES & set(activity.categories)) and "hotel" not in activity.categories


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
