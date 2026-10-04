"""Availability check: can two people book an activity on a given date?

- Funbooker: the listing's JSON API gives its items (per person or per plan)
  and the day's slots for the chosen quantities, without an account. The
  items that seat the party are tried in turn: a per-person item for 2, or a
  plan for 2 people ("Formule duo", "2 joueurs"). The listing's id and items
  are read at collection (known_check): an evening asks only for the slots.
- Wecandoo: the workshop's id is in its page, its public API lists the
  day's sessions with their seats taken.
- Come to Paris: the page lists the formulas; the booking form keeps its state
  in the session (cookie). Choosing a formula returns its bookable dates,
  choosing the date returns its hours and the ticket quantities on sale. Only
  the first step of a bundle ("Conciergerie + Bateaux-Mouches") is checked.

For the other sources, the booking engine is found at collection in the
activity's booking link or in the page it leads to (surprise.booking: its
booking's `check`), then asked through its public widget API:
- Zenchef (restaurants): the day's services and times open to 2 guests.
- SevenRooms (restaurants): the times bookable at once for 2, not the requests.
- 4escape (escape games, immersive games): each room's sessions with places
  left for 2, skipping rooms that need more players.
Bookeo is not checked: its booking pages sit behind a captcha.
"""

import argparse
import html
import json
import re
import threading
import time as clock
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from surprise.booking import PageChecks, Verdict
from surprise.collectors import come_to_paris, funbooker
from surprise.local_store import open_store

USER_AGENT = "Mozilla/5.0 (compatible; surprise-availability/0.1)"
DELAY_SECONDS = 1.0

FUNBOOKER_API = f"{funbooker.BASE_URL}/api/user/v1"
COME_TO_PARIS_AJAX = f"{come_to_paris.BASE_URL}/fre/ajax/booking.json.php"
ZENCHEF_API = "https://bookings-middleware.zenchef.com/getAvailabilities"
WECANDOO_EVENTS = "https://wecandoo.fr/api/ateliers/{}/events"
SEVENROOMS_API = "https://www.sevenrooms.com/api-yoa/availability/widget/range"

_WECANDOO_ID = re.compile(r"&quot;workshop&quot;:\{&quot;id&quot;:(\d+)")
_LEAST_PLAYERS = re.compile(r"\b(\d+)\s*(?:à|-)\s*\d+\s*(?:joueurs|personnes|pers\b)|à partir de (\d+)", re.IGNORECASE)
_FORMULA = re.compile(r'<div class="product_box ([^"]*)" data-product_id="(\d+)" data-name="\d+ - ([^"]*)"')
_LAYOUT_GROUPING = re.compile(r'name="layout_grouping_id"[^>]*value="(\d+)"')
_HOUR = re.compile(r'<input type="radio" value="(\d{2}:\d{2}):\d{2}" name="booking_hour"([^>]*)>')
# The main price's quantity list, then its "Complet" message (hidden while tickets are on sale).
_MAIN_PAX = re.compile(
    r'<select[^>]*class="[^"]*pax_selector[^"]*"[^>]*data-is_main_price="1"[^>]*>(.*?)</select>\s*'
    r'<div class="full_of_pax_message( hidden)?"',
    re.DOTALL,
)
_PAX_OPTION = re.compile(r'<option value="(\d+)"([^>]*)>')
_PARIS = ZoneInfo("Europe/Paris")
# Formulas that are not an outing to book on a date.
_SKIPPED_FORMULA = {"sold_out", "is_gift"}


@dataclass
class Availability:
    available: bool | None  # None: the source could not tell
    slots: list[str] = field(default_factory=list)  # "14:00", or "journée" when the day has no hours
    detail: str = ""  # the item or formula booked, or why it is not available


def check_funbooker(client: httpx.Client, listing: str, day: date, party: int = 2) -> Availability:
    """`listing`: its slug, or its slug, id and items read at collection (known_check): then only the slots are asked."""
    known = json.loads(listing) if listing.startswith("{") else None
    if known is None:
        response = client.get(f"{FUNBOOKER_API}/listing/{listing}", params={"locale": "fr"})
        response.raise_for_status()
        known = _funbooker_known(listing, response.json())
    candidates = _funbooker_capacities(known["items"], party)
    if not candidates:
        return Availability(False, detail=f"aucune formule pour {party}")
    refused = 0
    for label, capacities in candidates:
        response = client.post(
            f"{FUNBOOKER_API}/availabilities",
            json={"listingId": known["listing"], "capacities": capacities, "day": day.isoformat(), "includeAllFutureDates": False},
        )
        if response.status_code == 400:  # quantities refused by the listing
            refused += 1
            continue
        response.raise_for_status()
        slots = [
            "journée" if slot.get("allDay") else slot["localDateTimeStart"][11:16]
            for slot in response.json().get("availabilities") or []
            if slot.get("available") and (slot.get("capacity") is None or slot["capacity"] >= party)
        ]
        if slots:
            return Availability(True, slots, label)
    if refused == len(candidates) and listing.startswith("{"):
        # Items changed since the collection: the listing tells today's.
        return check_funbooker(client, known["slug"], day, party)
    return Availability(False, detail="complet ou fermé")


# Funbooker's site challenges a client past about 60 requests in a few seconds (Cloudflare): at collection, its
# listings are read one per second, as its pages are.
FUNBOOKER_LISTING_DELAY = 1.0
_funbooker_lock = threading.Lock()
_funbooker_next = 0.0
# What an item needs to tell whether it seats the party (_funbooker_capacities).
_FUNBOOKER_ITEM = ("id", "label", "priceType", "minCapacity", "maxCapacity", "numberOfPersons")


def _funbooker_known(slug: str, listing: dict[str, Any]) -> dict[str, Any]:
    """A listing's slug, id and bookable items: what a check asks the slots with, for any party."""
    items = [
        {key: item.get(key) for key in _FUNBOOKER_ITEM}
        for item in listing.get("listingItems") or [] if not item.get("isOption") and not item.get("isDisabled")
    ]
    return {"slug": slug, "listing": listing["id"], "items": items}


def _funbooker_listing(client: httpx.Client, url: str) -> Verdict | None:
    """A Funbooker listing's API read as a page's verdict (surprise.booking.PageChecks), kept a month: its slot check
    with the listing's id and items. None when it does not answer (asked again at the next collection)."""
    global _funbooker_next
    # The lock only books the next slot: the request runs outside it.
    with _funbooker_lock:
        clock.sleep(max(0.0, _funbooker_next - clock.monotonic()))
        _funbooker_next = clock.monotonic() + FUNBOOKER_LISTING_DELAY
    try:
        response = client.get(url, params={"locale": "fr"})
    except httpx.HTTPError:
        return None
    if not response.is_success:
        return None
    known = _funbooker_known(url.rsplit("/", 1)[1], response.json())
    return "Funbooker", False, "funbooker:" + json.dumps(known, ensure_ascii=False, separators=(",", ":"))


def known_check(client: httpx.Client, check: str | None, checks: PageChecks) -> str | None:
    """A slot check with what its engine needs, found at collection: a Funbooker listing's id and items, so that an
    evening asks only for the slots."""
    if not check or not check.startswith("funbooker:") or check.startswith("funbooker:{"):
        return check
    verdict = checks.get(client, f"{FUNBOOKER_API}/listing/{check.split(':', 1)[1]}", read=_funbooker_listing)
    return verdict[2] if verdict and verdict[2] else check


def _funbooker_capacities(items: list[dict[str, Any]], party: int) -> list[tuple[str, dict[str, int]]]:
    """Quantities to ask for, one item at a time: 2 of a per-person item, or 1 plan for 2."""
    candidates = []
    for item in items:
        if item.get("isOption") or item.get("isDisabled"):
            continue
        label = (item.get("label") or "").strip()
        # "Tarif 4 à 6 joueurs", "à partir de 4 personnes": the label asks more players than its capacities say.
        if (least := _LEAST_PLAYERS.search(label)) and int(least.group(1) or least.group(2)) > party:
            continue
        if item.get("priceType") == "per_person" and (item.get("minCapacity") or 0) <= party <= (item.get("maxCapacity") or 0):
            candidates.append((label, {str(item["id"]): party}))
        elif item.get("priceType") == "plan" and item.get("numberOfPersons") == party:
            candidates.append((label, {str(item["id"]): 1}))
    return candidates


def check_wecandoo(client: httpx.Client, workshop: str, day: date, party: int = 2) -> Availability:
    """`workshop`: its id, known at collection, else its page, which gives it."""
    if not workshop.isdigit():
        page = client.get(workshop)
        page.raise_for_status()
        if not (found := _WECANDOO_ID.search(page.text)):
            return Availability(None, detail="atelier introuvable")
        workshop = found.group(1)
    midnight = datetime(day.year, day.month, day.day, tzinfo=_PARIS)
    response = client.get(
        WECANDOO_EVENTS.format(workshop),
        params={"start": midnight.isoformat(), "end": (midnight + timedelta(days=1)).isoformat()},
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    slots = [
        f"{event['start'][11:16]}-{event['end'][11:16]}" if event.get("end") else event["start"][11:16]
        for event in response.json().get("data") or []
        if event.get("start", "")[:10] == day.isoformat()
        and not event.get("is_full")
        and (event.get("capacity") or 0) - (event.get("taken_seats") or 0) >= party
    ]
    if not slots:
        return Availability(False, detail="complet ou pas de séance")
    return Availability(True, sorted(slots))


def check_come_to_paris(client: httpx.Client, url: str, day: date, party: int = 2) -> Availability:
    # The form's state is in the session (cookie): each check its own, the others may run meanwhile.
    with httpx.Client(
        timeout=client.timeout, follow_redirects=client.follow_redirects, headers=client.headers, event_hooks=client.event_hooks,
    ) as session:
        return _check_come_to_paris(session, url, day, party)


def _check_come_to_paris(client: httpx.Client, url: str, day: date, party: int) -> Availability:
    page = client.get(url)
    page.raise_for_status()
    grouping = _LAYOUT_GROUPING.search(page.text)
    formulas = [(classes.split(), product_id, html.unescape(name).strip()) for classes, product_id, name in _FORMULA.findall(page.text)]
    if "<h2>Indisponible</h2>" in page.text:  # "Ce produit est complet": no formula on sale at all
        return Availability(False, detail="plus en vente")
    if not grouping or not formulas:
        return Availability(None, detail="formulaire de réservation introuvable")
    context = {
        "product_list": [product_id for _, product_id, _ in formulas],
        "layout_grouping_id": grouping.group(1),
        "option_form_fields_info": "",
        "product_form_fields_info": "",
    }
    headers = {"Referer": url, "X-Requested-With": "XMLHttpRequest"}
    unknown = False
    for classes, product_id, name in formulas:
        if _SKIPPED_FORMULA & set(classes):
            continue
        chosen = client.post(
            COME_TO_PARIS_AJAX,
            json={"action": "set_current_booking_product", "product_id": product_id, "unavailable": 0, **context},
            headers=headers,
        ).json()
        if chosen.get("no_api_response"):
            unknown = True
            continue
        if day.isoformat() not in (chosen.get("calendar_available_price") or {}) or day.isoformat() in (
            chosen.get("calendar_date_closings") or {}
        ):
            continue
        # The site sends the date both as midnight in Paris and as "2026-10-9".
        midnight = datetime(day.year, day.month, day.day, tzinfo=_PARIS)
        dated = client.post(
            COME_TO_PARIS_AJAX,
            json={
                "action": "set_current_booking_date",
                "date": int(midnight.timestamp()),
                "french_date": f"{day.year}-{day.month}-{day.day}",
                "product_id": product_id,
                **context,
            },
            headers=headers,
        ).json()
        if dated.get("has_no_disponibilities") or not _sells(dated.get("product_pax_form") or "", party):
            continue
        hours = [hour for hour, attributes in _HOUR.findall(dated.get("product_hour_form") or "") if "disabled" not in attributes]
        return Availability(True, hours or ["journée"], name)
    if unknown:
        return Availability(None, detail="billetterie momentanément indisponible")
    return Availability(False, detail="complet ou fermé")


def _sells(pax_form: str, party: int) -> bool:
    """The main price sells `party` tickets and is not marked "Complet"."""
    main = _MAIN_PAX.search(pax_form)
    if not main or not main.group(2):
        return False
    return any(int(value) >= party and "disabled" not in attributes for value, attributes in _PAX_OPTION.findall(main.group(1)))


def check_zenchef(client: httpx.Client, restaurant_id: str, day: date, party: int = 2) -> Availability:
    response = client.get(ZENCHEF_API, params={"restaurantId": restaurant_id, "date_begin": day.isoformat(), "date_end": day.isoformat()})
    response.raise_for_status()
    services, slots = [], []
    for shift in next(iter(response.json()), {}).get("shifts") or []:
        if shift.get("closed") or shift.get("marked_as_full"):
            continue
        times = [
            slot["name"]
            for slot in shift.get("shift_slots") or []
            if not slot.get("closed") and not slot.get("marked_as_full") and party in (slot.get("possible_guests") or [])
        ]
        if times:
            services.append(shift.get("name") or "")
            slots += times
    if not slots:
        return Availability(False, detail="complet ou fermé")
    return Availability(True, sorted(set(slots)), ", ".join(filter(None, services)))


def check_sevenrooms(client: httpx.Client, venue: str, day: date, party: int = 2) -> Availability:
    response = client.get(
        SEVENROOMS_API,
        # The whole day around 19:00, in 15 min steps.
        params={
            "venue": venue, "time_slot": "19:00", "party_size": party, "halo_size_interval": 100,
            "start_date": day.isoformat(), "num_days": 1, "channel": "SEVENROOMS_WIDGET",
        },
    )
    response.raise_for_status()
    services, slots = [], []
    for shift in (response.json().get("data") or {}).get("availability", {}).get(day.isoformat()) or []:
        # "request": a request the restaurant confirms later, not a table.
        times = [t["time_iso"][11:16] for t in shift.get("times") or [] if t.get("type") == "book" and t.get("time_iso")]
        if times and not shift.get("is_closed"):
            services.append(shift.get("name") or "")
            slots += times
    if not slots:
        return Availability(False, detail="complet ou fermé")
    return Availability(True, sorted(set(slots)), ", ".join(filter(None, services)))


def check_4escape(client: httpx.Client, domain: str, day: date, party: int = 2) -> Availability:
    """Rooms from the venue's settings (names, minimum players), then the day's sessions."""
    settings = client.get(f"https://{domain}/api/public/settings")
    settings.raise_for_status()
    rooms = settings.json().get("rooms") or {}
    sessions = client.post(f"https://{domain}/booking-data-json", json={"date": day.isoformat(), "viewDuration": 1})
    sessions.raise_for_status()
    names, slots = [], []
    for session in sessions.json().get("results") or []:
        room = rooms.get(session.get("roomId")) or {}
        minimum = min((c.get("minimum_players") or 0 for c in room.get("customer_categories_allowed") or []), default=0)
        # "booked" alone does not close a session: a taken one has no team or player left.
        if (
            session.get("disabled")
            or session.get("remainingTeams") == 0
            or (session.get("remainingPlayers") or 0) < party
            or minimum > party
        ):
            continue
        slots.append(session["start"][11:16])
        if (name := (room.get("name") or "").strip()) and name not in names:
            names.append(name)
    if not slots:
        return Availability(False, detail="complet ou fermé")
    return Availability(True, sorted(set(slots)), ", ".join(names))


# The engines asked for a date, by the name a booking's check gives them (surprise.booking.slot_check), and the
# name their answers are kept under.
CHECKERS = {
    "funbooker": ("Funbooker", check_funbooker),
    "wecandoo": ("Wecandoo", check_wecandoo),
    "come_to_paris": ("Come to Paris", check_come_to_paris),
    "zenchef": ("zenchef", check_zenchef),
    "sevenrooms": ("sevenrooms", check_sevenrooms),
    "4escape": ("4escape", check_4escape),
}


def check(client: httpx.Client, activity: dict[str, Any], day: date, party: int) -> tuple[str, Availability] | None:
    """The engine checked and its answer; None when no engine tells the activity's slots (its booking's check, found
    at collection: no page to read for it now)."""
    found = (activity["activity"].get("booking") or {}).get("check")
    if not found:
        return None
    engine, key = found.split(":", 1)
    name, checker = CHECKERS[engine]
    return name, checker(client, key, day, party)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("day", type=date.fromisoformat, help="date à vérifier, AAAA-MM-JJ")
    parser.add_argument("--party", type=int, default=2, help="nombre de personnes (2 par défaut)")
    parser.add_argument("--source", action="append", help="ne vérifier que cette source (répétable)")
    parser.add_argument("--limit", type=int, help="nombre maximum d'activités vérifiées")
    args = parser.parse_args()

    with open_store() as store:
        activities = [
            a for a in store.list_for_moderation()
            if a["status"] not in ("rejected", "filtered") and (not args.source or a["source_id"] in args.source)
        ][: args.limit]

    results = Counter()
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        for activity in activities:
            try:
                checked = check(client, activity, args.day, args.party)
            except (httpx.HTTPError, ValueError) as error:
                checked = "?", Availability(None, detail=f"erreur : {error}")
            if not checked:
                results["sans moteur"] += 1
                continue
            engine, result = checked
            mark = {True: "✓", False: "✗", None: "?"}[result.available]
            results[mark] += 1
            slots = ", ".join(result.slots)
            print(f"{mark} [{engine}] {activity['activity']['title']} — {' · '.join(filter(None, [slots, result.detail]))}")
            clock.sleep(DELAY_SECONDS)
    print(
        f"{args.day:%d/%m/%Y}, {args.party} personnes : {results['✓']} disponibles, {results['✗']} non, "
        f"{results['?']} inconnues ; {results['sans moteur']} sans moteur de réservation pris en charge"
    )


if __name__ == "__main__":
    main()
