"""Availability check: can two people book an activity on a given date?

- Funbooker: the listing's JSON API gives its items (per person or per plan)
  and the day's slots for the chosen quantities, without an account. The
  items that seat two are tried in turn: a per-person item for 2, or a plan
  for 2 people ("Formule duo", "2 joueurs").
- Wecandoo: the workshop's id is in its page, its public API lists the
  day's sessions with their seats taken.
- Come to Paris: the page lists the formulas; the booking form keeps its state
  in the session (cookie). Choosing a formula returns its bookable dates,
  choosing the date returns its hours and the ticket quantities on sale. Only
  the first step of a bundle ("Conciergerie + Bateaux-Mouches") is checked.

For the other sources, the booking engine is found in the activity's booking
link or in the page it leads to, then asked through its public widget API:
- Zenchef (restaurants): the day's services and times open to 2 guests.
- SevenRooms (restaurants): the times bookable at once for 2, not the requests.
- 4escape (escape games, immersive games): each room's sessions with places
  left for 2, skipping rooms that need more players.
Bookeo is not checked: its booking pages sit behind a captcha.
"""

import argparse
import base64
import html
import json
import re
import time as clock
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from surprise.collectors import come_to_paris, funbooker, wecandoo
from surprise.local_store import open_store

USER_AGENT = "Mozilla/5.0 (compatible; surprise-availability/0.1)"
DELAY_SECONDS = 1.0

FUNBOOKER_API = f"{funbooker.BASE_URL}/api/user/v1"
COME_TO_PARIS_AJAX = f"{come_to_paris.BASE_URL}/fre/ajax/booking.json.php"
ZENCHEF_API = "https://bookings-middleware.zenchef.com/getAvailabilities"
WECANDOO_EVENTS = "https://wecandoo.fr/api/ateliers/{}/events"
SEVENROOMS_API = "https://www.sevenrooms.com/api-yoa/availability/widget/range"

# Booking engines found in a link or in the page it leads to, with the venue's id there.
_ZENCHEF_ID = re.compile(r"bookings\.zenchef\.com/[^\"'\s<>]*?[?&](?:amp;)?rid=(\d+)|data-restaurant(?:-id)?=[\"'](\d+)")
_SEVENROOMS_VENUE = re.compile(r"sevenrooms\.com/reservations/([\w-]+)")
_4ESCAPE_SETTINGS = re.compile(r'class="forescape-[\w-]+"[^>]*data-settings="b64\.([A-Za-z0-9+/=]+)"')
_4ESCAPE_SUBDOMAIN = re.compile(r'class="forescape"[^>]*data-subdomain="([\w-]+)"')
_4ESCAPE_DOMAIN = re.compile(r"(?<![\w-])(?!www\.)[\w-]+\.4escape\.io\b")

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


def check_funbooker(client: httpx.Client, slug: str, day: date, party: int = 2) -> Availability:
    response = client.get(f"{FUNBOOKER_API}/listing/{slug}", params={"locale": "fr"})
    response.raise_for_status()
    listing = response.json()
    candidates = _funbooker_capacities(listing.get("listingItems") or [], party)
    if not candidates:
        return Availability(False, detail=f"aucune formule pour {party}")
    for label, capacities in candidates:
        response = client.post(
            f"{FUNBOOKER_API}/availabilities",
            json={"listingId": listing["id"], "capacities": capacities, "day": day.isoformat(), "includeAllFutureDates": False},
        )
        if response.status_code == 400:  # quantities refused by the listing
            continue
        response.raise_for_status()
        slots = [
            "journée" if slot.get("allDay") else slot["localDateTimeStart"][11:16]
            for slot in response.json().get("availabilities") or []
            if slot.get("available") and (slot.get("capacity") is None or slot["capacity"] >= party)
        ]
        if slots:
            return Availability(True, slots, label)
    return Availability(False, detail="complet ou fermé")


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


def check_wecandoo(client: httpx.Client, url: str, day: date, party: int = 2) -> Availability:
    page = client.get(url)
    page.raise_for_status()
    if not (workshop := _WECANDOO_ID.search(page.text)):
        return Availability(None, detail="atelier introuvable")
    midnight = datetime(day.year, day.month, day.day, tzinfo=_PARIS)
    response = client.get(
        WECANDOO_EVENTS.format(workshop.group(1)),
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


ENGINE_CHECKERS = {"zenchef": check_zenchef, "sevenrooms": check_sevenrooms, "4escape": check_4escape}


def find_engine(client: httpx.Client, urls: list[str]) -> tuple[str, str] | None:
    """The booking engine behind the activity's links and its id there: in a link, else in the linked page."""
    for url in urls:
        if engine := _engine_in(url):
            return engine
    for url in urls:
        try:
            page = client.get(url)
        except httpx.HTTPError:
            continue
        if page.is_success and (engine := _engine_in(page.text)):
            return engine
    return None


def _engine_in(text: str) -> tuple[str, str] | None:
    if match := _ZENCHEF_ID.search(text):
        return "zenchef", match.group(1) or match.group(2)
    if match := _SEVENROOMS_VENUE.search(text):
        return "sevenrooms", match.group(1)
    if match := _4ESCAPE_SETTINGS.search(text):
        try:
            return "4escape", json.loads(base64.b64decode(match.group(1)))["domain"]
        except (ValueError, KeyError):
            pass
    if match := _4ESCAPE_SUBDOMAIN.search(text):
        return "4escape", f"{match.group(1)}.4escape.io"
    if match := _4ESCAPE_DOMAIN.search(text):
        return "4escape", match.group(0)
    return None


def check(client: httpx.Client, activity: dict[str, Any], day: date, party: int) -> tuple[str, Availability] | None:
    """The engine checked and its answer; None when the activity's booking goes through no supported engine."""
    if activity["source_id"] == funbooker.SOURCE_ID:
        return "Funbooker", check_funbooker(client, activity["external_id"], day, party)
    if activity["source_id"] == wecandoo.SOURCE_ID:
        return "Wecandoo", check_wecandoo(client, activity["source_url"], day, party)
    if activity["source_id"] == come_to_paris.SOURCE_ID:
        return "Come to Paris", check_come_to_paris(client, activity["source_url"], day, party)
    urls = [offer["booking_url"] for offer in activity["activity"].get("offers") or [] if offer.get("booking_url")]
    urls += [activity["enrichment"]["booking_url"]] if activity["enrichment"].get("booking_url") else []
    # The official site often embeds the widget (a restaurant's Zenchef button).
    urls += [activity["activity"]["website"]] if activity["activity"].get("website") else []
    if not (found := find_engine(client, list(dict.fromkeys(urls)))):
        return None
    engine, key = found
    return engine, ENGINE_CHECKERS[engine](client, key, day, party)


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
