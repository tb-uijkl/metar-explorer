"""METAR Explorer: an educational weather reader and wind-component calculator.

Python standard library only. Uses NOAA Aviation Weather Center's parsed METAR JSON.
Not intended for operational flight planning.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://aviationweather.gov/api/data/metar"
EXAMPLE_FILE = Path(__file__).with_name("sample_metar.json")

CLOUD_NAMES = {
    "SKC": "Sky clear", "CLR": "Clear", "FEW": "Few",
    "SCT": "Scattered", "BKN": "Broken", "OVC": "Overcast", "VV": "Vertical visibility",
}


def load_metar(airport: str, demo: bool = False) -> dict:
    """Return one latest METAR record. Demo mode works without the internet."""
    if demo:
        with EXAMPLE_FILE.open(encoding="utf-8") as f:
            return json.load(f)

    query = urlencode({"ids": airport, "format": "json"})
    request = Request(
        f"{API_URL}?{query}",
        headers={"User-Agent": "METARExplorer-StudentProject/0.1 (educational use)"},
    )
    try:
        with urlopen(request, timeout=12) as response:
            if response.status == 204:
                raise ValueError(f"No recent METAR found for {airport}.")
            records = json.load(response)
    except HTTPError as exc:
        raise ValueError(f"Weather service returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ValueError(f"Could not reach the weather service: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Weather service returned invalid JSON.") from exc

    if not isinstance(records, list) or not records:
        raise ValueError(f"No recent METAR found for {airport}.")
    return records[0]


def observation_time(record: dict) -> str:
    """AWC usually reports obsTime as a Unix timestamp (seconds)."""
    value = record.get("obsTime")
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if isinstance(value, str) and value:
        return value
    return str(record.get("reportTime") or "unknown")


def fmt(value, suffix: str = "") -> str:
    if value is None or value == "":
        return "not reported"
    return f"{value}{suffix}"


def wind_components(wind_from_true: float, speed_kt: float,
                    runway_magnetic: float, variation_east: float) -> tuple[float, float]:
    """Return headwind and signed crosswind (right-positive), in knots.

    METAR wind directions are TRUE. Runway numbers/headings are MAGNETIC.
    Convert runway to true heading: true = magnetic + east variation.
    """
    runway_true = (runway_magnetic + variation_east) % 360
    angle = math.radians((wind_from_true - runway_true + 180) % 360 - 180)
    return speed_kt * math.cos(angle), speed_kt * math.sin(angle)


def parse_runway(value: str) -> int:
    """For a label like 07, 07L, or 18R, return its approximate magnetic heading."""
    runway = value.strip().upper()
    digits = runway[:-1] if runway.endswith(("L", "C", "R")) else runway
    if not digits.isdigit() or not (1 <= int(digits) <= 36):
        raise argparse.ArgumentTypeError("Runway must be 01–36, optionally followed by L/C/R.")
    return int(digits) * 10 % 360


def describe_components(headwind: float, crosswind: float) -> str:
    longitudinal = f"Headwind {headwind:.1f} kt" if headwind >= 0 else f"Tailwind {-headwind:.1f} kt"
    direction = "right" if crosswind > 0.01 else "left" if crosswind < -0.01 else "neither side"
    return f"{longitudinal} | Crosswind {abs(crosswind):.1f} kt (from {direction})"


def print_weather(record: dict, airport: str, runway: str | None,
                  variation: float | None, demo: bool) -> None:
    print("=" * 58)
    print("METAR EXPLORER — educational demo" if demo else "METAR EXPLORER — NOAA observation")
    print("=" * 58)
    print(f"Station:      {record.get('icaoId') or airport} — {record.get('name') or 'Airport'}")
    print(f"Observed:     {observation_time(record)}")
    print(f"Raw METAR:    {record.get('rawOb') or 'not reported'}")

    wind_dir = record.get("wdir")
    wind_speed = record.get("wspd")
    gust = record.get("wgst")
    if str(wind_dir).upper() == "VRB":
        dir_text = "Variable"
    elif wind_dir is None:
        dir_text = "Not reported"
    else:
        try:
            dir_text = f"{float(wind_dir):.0f}° true"
        except (TypeError, ValueError):
            dir_text = str(wind_dir)
    print(f"Wind:         {dir_text}, {fmt(wind_speed, ' kt')}", end="")
    if gust is not None:
        print(f", gust {gust} kt")
    else:
        print()

    print(f"Visibility:   {fmt(record.get('visib'), ' statute miles')}")

    temp_c = record.get("temp")

    if temp_c is not None:
        temp_f = float(temp_c) * 9 / 5 + 32
        print(f"Temperature:  {temp_c} °C / {temp_f:.1f} °F")
    else:
        print("Temperature:  not reported")

    print(f"Dew point:    {fmt(record.get('dewp'), ' °C')}")
    print(f"Altimeter:    {fmt(record.get('altim'), ' hPa')}")
    print(f"Weather:      {fmt(record.get('wxString'))}")
    clouds = record.get("clouds") or []
    if clouds:
        layer_text = []
        for c in clouds:
            cover = CLOUD_NAMES.get(c.get("cover"), c.get("cover", "unknown"))
            base = c.get("base")
            layer_text.append(f"{cover} {base:,} ft AGL" if isinstance(base, (int, float)) else cover)
        print(f"Cloud layers: {', '.join(layer_text)}")
    else:
        print("Cloud layers: not reported")

    if not runway:
        print("\nTip: Add --runway 18 for a simple wind-component estimate.")
        return

    runway_heading = parse_runway(runway)
    print(f"\nRUNWAY {runway.upper()} WIND COMPONENTS")
    if variation is None:
        variation = 0.0
        print("WARNING: Using 0° magnetic variation (approximation only).")
        print("         Enter --variation +N for east or -N for west variation.")
    try:
        numeric_dir = float(wind_dir)
        numeric_speed = float(wind_speed)
    except (TypeError, ValueError):
        print("Cannot calculate: wind direction is variable or unavailable.")
        return
    headwind, crosswind = wind_components(numeric_dir, numeric_speed, runway_heading, variation)
    print("Sustained:    " + describe_components(headwind, crosswind))
    if gust is not None:
        try:
            headwind_g, crosswind_g = wind_components(numeric_dir, float(gust), runway_heading, variation)
            print("At gust:     " + describe_components(headwind_g, crosswind_g))
        except (TypeError, ValueError):
            pass
    print("\nEstimates only: runway numbers are approximate magnetic headings.")
    print("NOT for real-world flight planning or go/no-go decisions.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read METARs and estimate runway wind components.")
    parser.add_argument("airport", nargs="?", default="RJOO", help="4-letter ICAO station (default: RJOO)")
    parser.add_argument("--runway", type=str, help="Runway designator, e.g. 18 or 07L")
    parser.add_argument("--variation", type=float,
                        help="Local magnetic variation in degrees: east positive, west negative")
    parser.add_argument("--demo", action="store_true", help="Use included fictional weather (no internet)")
    args = parser.parse_args()

    airport = args.airport.upper()
    if len(airport) != 4 or not airport.isalpha():
        parser.error("Enter a four-letter ICAO station code, such as RJOO or KJFK.")
    if args.runway is not None:
        try:
            parse_runway(args.runway)
        except argparse.ArgumentTypeError as exc:
            parser.error(str(exc))
    if args.variation is not None and not (-180 <= args.variation <= 180):
        parser.error("Magnetic variation must be between -180 and 180 degrees.")

    try:
        record = load_metar(airport, demo=args.demo)
        print_weather(record, airport, args.runway, args.variation, args.demo)
        return 0
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Try: python3 metar_tool.py RJOO --runway 18 --demo", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
