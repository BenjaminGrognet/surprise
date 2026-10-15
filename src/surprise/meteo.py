"""The weather of an evening's steps out in the open (docs/complicite.md, B10): 48 hours before, the chance of rain at
each step's place and hour, from Open-Meteo's hourly forecast (free and without a key for a use that is not
commercial: https://open-meteo.com/en/terms). Likely rain (RAINY percent or more) on such a step: the instigateur is
told, by email and on the web, and offered the plan B the app already has (surprise.courriers). Nothing is changed
without them: their bookings are theirs.

    uv run python -m surprise.meteo 48.8566 2.3522 2026-10-16T21:00   # the chance of rain there, then
"""

import argparse
import time as clock
from datetime import datetime
from typing import Any, Callable

import httpx

FORECAST = "https://api.open-meteo.com/v1/forecast"
RAINY = 60  # percent: from there, a plan B is offered
# Open-Meteo forecasts sixteen days ahead; asked two days before, one call per place and day.
Fetch = Callable[[float, float, str], dict[str, Any] | None]


def fetch(lat: float, lon: float, day: str, client: httpx.Client | None = None) -> dict[str, Any] | None:
    """The hourly chances of rain at a place on a day (Paris time), or None if Open-Meteo cannot be read."""
    params = {
        "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "hourly": "precipitation_probability",
        "timezone": "Europe/Paris", "start_date": day, "end_date": day,
    }
    try:
        if client:
            response = client.get(FORECAST, params=params)
        else:
            with httpx.Client(timeout=15) as own:
                response = own.get(FORECAST, params=params)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        return None


_KEPT: dict[tuple[float, float, str], tuple[float, dict[str, Any] | None]] = {}
KEEP_SECONDS = 3 * 3600  # a forecast read again every three hours at most: the emails pass every ten minutes


def cached(lat: float, lon: float, day: str) -> dict[str, Any] | None:
    """`fetch`, its answer kept a few hours per place (to the hundredth of a degree) and day."""
    key = (round(lat, 2), round(lon, 2), day)
    if key in _KEPT and clock.monotonic() - _KEPT[key][0] < KEEP_SECONDS:
        return _KEPT[key][1]
    forecast = fetch(lat, lon, day)
    _KEPT[key] = (clock.monotonic(), forecast)
    return forecast


def rain_chance(forecast: dict[str, Any] | None, at: datetime) -> int | None:
    """The chance of rain in the hour of `at` (Paris time), in percent; None if the forecast does not say."""
    hourly = (forecast or {}).get("hourly") or {}
    wanted = at.strftime("%Y-%m-%dT%H:00")
    for time, chance in zip(hourly.get("time") or [], hourly.get("precipitation_probability") or []):
        if time == wanted and isinstance(chance, (int, float)):
            return int(chance)
    return None


def rainy_steps(route: dict[str, Any], get: Fetch = fetch) -> list[tuple[dict[str, Any], int]]:
    """The steps out in the open where rain is likely at their hour, with its chance: one forecast per place and day."""
    found, asked = [], {}
    for step in route.get("steps") or []:
        if not step.get("outdoor") or step.get("lat") is None:
            continue
        start = datetime.fromisoformat(step["start"])
        key = (round(step["lat"], 2), round(step["lon"], 2), start.date().isoformat())
        if key not in asked:
            asked[key] = get(step["lat"], step["lon"], key[2])
        chance = rain_chance(asked[key], start)
        if chance is not None and chance >= RAINY:
            found.append((step, chance))
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description="La probabilité de pluie à un endroit, à une heure (Open-Meteo)")
    parser.add_argument("lat", type=float)
    parser.add_argument("lon", type=float)
    parser.add_argument("at", help="l'heure, à Paris : 2026-10-16T21:00")
    args = parser.parse_args()
    at = datetime.fromisoformat(args.at)
    chance = rain_chance(fetch(args.lat, args.lon, at.date().isoformat()), at)
    print("Prévision indisponible" if chance is None else f"{chance} % de risque de pluie")


if __name__ == "__main__":
    main()
