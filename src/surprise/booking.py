"""Online booking: is an activity really bookable, through a known ticketing or booking site?

A booking link counts when it leads to a ticketing or booking platform (Fever,
Billetweb, Zenchef…), a venue's own ticketing ("billetterie.", "tickets."
subdomains), or a venue page that embeds a booking widget (Bookeo, 4escape,
Zenchef…). A link to a venue's home page or information page does not.

Bars, clubs and restaurants need no booking: a couple can walk in while they are open.
"""

import base64
import json
import re
import threading
from collections import defaultdict
from collections.abc import Callable, Iterable
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
    "Notre Billetterie": r"(?<![\w-])[\w-]+\.notre-billetterie\.com",
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
    "Qweekle": r"(?<![\w-])[\w-]+\.qweekle\.com",
    # WordPress "Event Tickets": the venue sells its seats on the event's page ("Le Son de la Terre").
    "Event Tickets": r"id=\"tribe-tickets__tickets-form\"",
    "SimplyBook": r"simplybook\.(?:it|me)",
    "Zenchef": r"bookings\.zenchef\.com|widget\.zenchef\.com|sdk\.zenchef\.com",
    "TheFork": r"thefork\.fr|lafourchette\.com",
    "SevenRooms": r"sevenrooms\.com/(?:reservations|explore)",
    "OpenTable": r"opentable\.(?:fr|com)/(?:r/|restref|booking)",
    "Guestonline": r"guestonline\.(?:io|fr)",
    "Resy": r"resy\.com/cities",
    # A bar's tables booked for a group, free, from its page.
    "Privateaser": r"privateaser\.com/lieu/\d+",
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
    r"forms\.gle/|docs\.google\.com/forms/|tally\.so/r/|(?<![\w-])[\w-]+\.typeform\.com/to/|form\.jotform\.com/|framaforms\.org/",
    re.IGNORECASE,
)
_ASKS_BOOKING = re.compile(r"r[ée]serv|inscri", re.IGNORECASE)
_HOST = re.compile(r"https?://([a-z0-9.-]+)", re.IGNORECASE)


def engine_in(text: str) -> str | None:
    """The first known platform named in a link or a page."""
    return next((name for name, pattern in _ENGINE_PATTERNS.items() if pattern.search(text)), None)


# Engines surprise.availability asks for a date, and the activity's id there: in a booking widget…
_ZENCHEF_ID = re.compile(r"bookings\.zenchef\.com/[^\"'\s<>]*?[?&](?:amp;)?rid=(\d+)|data-restaurant(?:-id)?=[\"'](\d+)")
_SEVENROOMS_VENUE = re.compile(r"sevenrooms\.com/reservations/([\w-]+)")
_4ESCAPE_SETTINGS = re.compile(r'class="forescape-[\w-]+"[^>]*data-settings="b64\.([A-Za-z0-9+/=]+)"')
_4ESCAPE_SUBDOMAIN = re.compile(r'class="forescape"[^>]*data-subdomain="([\w-]+)"')
_4ESCAPE_DOMAIN = re.compile(r"(?<![\w-])(?!www\.)[\w-]+\.4escape\.io\b")
# … or a platform's listing, by its link.
_LISTINGS = {
    "funbooker": re.compile(r"funbooker\.com/[a-z]{2}/annonce/([\w-]+)"),
    "wecandoo": re.compile(r"https://wecandoo\.fr/atelier/[\w-]+"),
    "come_to_paris": re.compile(r"https://www\.cometoparis\.com/[a-z]{3}/[\w-]+/[\w-]+-m\d+"),
}
# Engines whose page gives the activity's id (a widget), worth reading for it.
WIDGET_ENGINES = {"Zenchef", "SevenRooms", "4escape"}


def slot_check(text: str, link: bool = False) -> str | None:
    """The engine surprise.availability asks for a date and the activity's id there ("zenchef:351778",
    "funbooker:atelier-gravure"): from a booking widget in a page or link, from a platform's listing in a link only."""
    if match := _ZENCHEF_ID.search(text):
        return f"zenchef:{match.group(1) or match.group(2)}"
    if match := _SEVENROOMS_VENUE.search(text):
        return f"sevenrooms:{match.group(1)}"
    if match := _4ESCAPE_SETTINGS.search(text):
        try:
            return f"4escape:{json.loads(base64.b64decode(match.group(1)))['domain']}"
        except (ValueError, KeyError):
            pass
    if match := _4ESCAPE_SUBDOMAIN.search(text):
        return f"4escape:{match.group(1)}.4escape.io"
    if match := _4ESCAPE_DOMAIN.search(text):
        return f"4escape:{match.group(0)}"
    for engine, pattern in _LISTINGS.items() if link else ():
        if match := pattern.search(text):
            return f"{engine}:{match.group(match.lastindex or 0)}"
    return None


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


# What a page says: the booking engine it leads to, whether the place has closed, and its slot check (slot_check).
Verdict = tuple[str | None, bool, str | None]


def page_verdict(client: httpx.Client, url: str) -> Verdict | None:
    """What a page says (Verdict); None if unreachable."""
    # Imported here: the enrichment imports the collectors, which check bookings with this module.
    from surprise.enrich import booking_link

    page = _get(client, url)
    if page is None:
        return None
    closed = bool(CLOSED.search(page.text))
    engine = (
        engine_in(str(page.url)) or engine_in(page.text) or booking_form(str(page.url), page.text)
        or ticketing_of_site(str(page.url), page.text)
    )
    check = slot_check(str(page.url), link=True) or slot_check(page.text)
    # The site's "Réserver" page ("perpette.com/reserver/") embeds the widget, or the id of the one the site names.
    if (not engine or engine in WIDGET_ENGINES and not check) and (link := booking_link(str(page.url), page.text)):
        engine, check = engine or own_ticketing(link), check or slot_check(link, link=True)
        if (not engine or engine in WIDGET_ENGINES and not check) and (linked := _get(client, link)):
            engine = engine or engine_in(str(linked.url)) or engine_in(linked.text) or ticketing_of_site(str(linked.url), linked.text)
            check = check or slot_check(str(linked.url), link=True) or slot_check(linked.text)
    return engine, closed, check


class PageChecks:
    """Page verdicts of a collection run, each page read once: 46 concerts of a club check its site once.

    Shared by threads: one page at a time per site. `known` are verdicts kept in the store; `new` the ones to save.
    """

    def __init__(self, known: dict[str, Verdict] | None = None) -> None:
        self.verdicts: dict[str, Verdict | None] = dict(known or {})
        self.new: dict[str, Verdict] = {}
        self._lock = threading.Lock()
        self._hosts: dict[str, threading.Lock] = defaultdict(threading.Lock)

    def get(self, client: httpx.Client, url: str, read: Callable[[httpx.Client, str], Verdict | None] = page_verdict) -> Verdict | None:
        """The url's verdict, `read` once (a page, by default; an engine's API too)."""
        if url not in self.verdicts:
            with self._lock:
                host = self._hosts[urlsplit(url).hostname or ""]
            with host:
                if url not in self.verdicts:
                    verdict = self.verdicts[url] = read(client, url)
                    if verdict is not None:
                        with self._lock:
                            self.new[url] = verdict
        return self.verdicts[url]

    def take_new(self) -> dict[str, Verdict]:
        """The verdicts read since the last call, to save, while other threads go on reading pages."""
        with self._lock:
            new, self.new = self.new, {}
        return new


def booking_found(client: httpx.Client, urls: Iterable[str], checks: PageChecks | None = None) -> tuple[str, str | None] | None:
    """Where the activity can be booked online, and its slot check when an engine answers for a date (slot_check):
    in its links first, then in the pages they lead to."""
    urls = list(dict.fromkeys(urls))
    checks = checks or PageChecks()
    for url in urls:
        if engine := engine_in(url) or own_ticketing(url):
            # A widget's link without the venue's id ("widget.zenchef.com/…"): its pages may give it.
            pages = (verdict[2] for u in urls if engine in WIDGET_ENGINES and (verdict := checks.get(client, u)))
            return engine, slot_check(url, link=True) or next(filter(None, pages), None)
    for url in urls:
        if (verdict := checks.get(client, url)) and verdict[0]:
            return verdict[0], verdict[2]
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


def is_open(client: httpx.Client, activity: Activity, source_text: str = "", checks: PageChecks | None = None) -> bool:
    """Neither the source nor the official site says the place has closed for good."""
    if CLOSED.search(source_text):
        return False
    verdict = (checks or PageChecks()).get(client, str(activity.website)) if activity.website else None
    return not (verdict and verdict[1])


def booking_urls(activity: Activity) -> list[str]:
    """Booking links first, then the official site, whose "Réserver" button or widget often leads to the platform."""
    urls = [str(offer.booking_url) for offer in activity.offers if offer.booking_url]
    return urls + [str(activity.website)] if activity.website else urls
