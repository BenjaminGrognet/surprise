"""Availability check: can two people book an activity on a given date?

- Funbooker: the listing's JSON API gives its items (per person or per plan)
  and the day's slots for the chosen quantities, without an account. The
  items that seat two are tried in turn: a per-person item for 2, or a plan
  for 2 people ("Formule duo", "2 joueurs").
- Come to Paris: the page lists the formulas; the booking form keeps its state
  in the session (cookie). Choosing a formula returns its bookable dates,
  choosing the date returns its hours and the ticket quantities on sale. Only
  the first step of a bundle ("Conciergerie + Bateaux-Mouches") is checked.

Other sources are not checked: their activities are reported as unknown.
"""

import argparse
import html
import re
import time as clock
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from surprise.collectors import come_to_paris, funbooker
from surprise.local_store import LocalStore

USER_AGENT = "Mozilla/5.0 (compatible; surprise-availability/0.1)"
DELAY_SECONDS = 1.0

FUNBOOKER_API = f"{funbooker.BASE_URL}/api/user/v1"
COME_TO_PARIS_AJAX = f"{come_to_paris.BASE_URL}/fre/ajax/booking.json.php"

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
        if item.get("priceType") == "per_person" and (item.get("minCapacity") or 0) <= party <= (item.get("maxCapacity") or 0):
            candidates.append((label, {str(item["id"]): party}))
        elif item.get("priceType") == "plan" and item.get("numberOfPersons") == party:
            candidates.append((label, {str(item["id"]): 1}))
    return candidates


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


CHECKERS = {
    funbooker.SOURCE_ID: lambda client, activity, day, party: check_funbooker(client, activity["external_id"], day, party),
    come_to_paris.SOURCE_ID: lambda client, activity, day, party: check_come_to_paris(client, activity["source_url"], day, party),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("day", type=date.fromisoformat, help="date à vérifier, AAAA-MM-JJ")
    parser.add_argument("--party", type=int, default=2, help="nombre de personnes (2 par défaut)")
    parser.add_argument("--source", action="append", choices=sorted(CHECKERS), help="ne vérifier que cette source (répétable)")
    parser.add_argument("--limit", type=int, help="nombre maximum d'activités vérifiées")
    args = parser.parse_args()

    sources = args.source or sorted(CHECKERS)
    with LocalStore() as store:
        activities = [
            a for a in store.list_for_moderation() if a["source_id"] in sources and a["status"] != "rejected"
        ][: args.limit]

    results = Counter()
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        for activity in activities:
            try:
                result = CHECKERS[activity["source_id"]](client, activity, args.day, args.party)
            except (httpx.HTTPError, ValueError) as error:
                result = Availability(None, detail=f"erreur : {error}")
            mark = {True: "✓", False: "✗", None: "?"}[result.available]
            results[mark] += 1
            slots = ", ".join(result.slots)
            print(f"{mark} {activity['activity']['title']} — {' · '.join(filter(None, [slots, result.detail]))}")
            clock.sleep(DELAY_SECONDS)
    print(f"{args.day:%d/%m/%Y}, {args.party} personnes : {results['✓']} disponibles, {results['✗']} non, {results['?']} inconnues")


if __name__ == "__main__":
    main()
