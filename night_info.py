#!/usr/bin/env python3
"""
night_info.py — Tonight's sunset, astronomical twilight, moon phase, and hours of darkness.

Uses IP geolocation to find your location (override with --lat/--lon).
Requires: pip install astral

Examples:
  python night_info.py
  python night_info.py --lat 40.26 --lon -80.19
  python night_info.py --date 2026-07-04
"""

import argparse
import datetime as dt
import json
import math
import sys
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

try:
    from astral import LocationInfo
    from astral.sun import sun, dusk, dawn
    from astral.moon import phase as moon_phase
except ImportError:
    print("Error: missing 'astral' package.")
    print("Install it with:  pip install astral")
    sys.exit(1)

# Fallback location (used if IP lookup fails)
FALLBACK = {
    "lat": 40.2626,
    "lon": -80.1873,
    "city": "Canonsburg",
    "region": "PA",
    "tzname": "America/New_York",
}


def get_location_from_ip(timeout: int = 6):
    """Return (lat, lon, city, region, tzname) from ip-api.com, or None on failure.

    Note: the free ip-api.com tier is HTTP-only (no TLS) and rate-limited
    (~45 req/min); on any failure we return None and the caller falls back.
    """
    url = "http://ip-api.com/json/?fields=lat,lon,city,regionName,timezone,status,message"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "night_info.py"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("status") != "success":
            return None
        return (
            float(data["lat"]),
            float(data["lon"]),
            data.get("city", "Unknown"),
            data.get("regionName", ""),
            data.get("timezone", "UTC"),
        )
    except (urllib.error.URLError, ValueError, KeyError, json.JSONDecodeError):
        return None


def parse_args():
    p = argparse.ArgumentParser(description="Sunset, astronomical twilight, moon, and darkness info.")
    p.add_argument("--lat", type=float, help="Latitude (decimal degrees)")
    p.add_argument("--lon", type=float, help="Longitude (decimal degrees, negative for west)")
    p.add_argument("--tz", dest="tzname", help="IANA timezone name (e.g. America/New_York)")
    p.add_argument("--date", help="Compute for a specific local date (YYYY-MM-DD) instead of 'tonight'")
    args = p.parse_args()
    if (args.lat is None) != (args.lon is None):
        p.error("--lat and --lon must be provided together")
    return args


def fmt_time(d) -> str:
    """12-hour time without leading zero, plus TZ abbreviation."""
    if d is None:
        return "—"
    s = d.strftime("%I:%M %p")
    if s.startswith("0"):
        s = s[1:]
    tz_abbr = d.tzname() or ""
    return f"{s} {tz_abbr}"


def find_best_event(observer, event_type: str, reference: dt.datetime, tz: ZoneInfo, depression: float = 18) -> dt.datetime | None:
    """Find the most relevant sun event relative to 'reference' time.

    For sunset: prefers the most recent past sunset if it was less than ~16h ago
    (i.e. we are still in that night), otherwise the next upcoming sunset.
    For dusk/dawn: prefers the soonest event at/after the reference.
    This logic is robust against large timezone offsets.
    """
    func = {"sunset": sun, "dusk": dusk, "dawn": dawn}[event_type]
    kwargs = {"depression": depression} if event_type in ("dusk", "dawn") else {}

    candidates: list[dt.datetime] = []
    base = reference.date()
    for delta in range(-2, 3):
        d = base + dt.timedelta(days=delta)
        try:
            if event_type == "sunset":
                val = func(observer, date=d)["sunset"].astimezone(tz)
            else:
                val = func(observer, date=d, **kwargs).astimezone(tz)
            candidates.append(val)
        except (ValueError, KeyError):
            continue

    if not candidates:
        return None

    if event_type == "sunset":
        # "Tonight" semantics:
        # Use the most recent past sunset only if it was less than ~16 hours ago
        # (handles late night + early morning, including long winter nights, while
        # still preferring the current day's sunset once we are well into daytime).
        past = [c for c in candidates if c <= reference]
        if past:
            recent = max(past)
            if (reference - recent).total_seconds() < 16 * 3600:
                return recent
        # Otherwise pick the next upcoming sunset
        upcoming = [c for c in candidates if c > reference]
        if upcoming:
            return min(upcoming)
        return max(candidates)

    # For dusk and dawn, prefer the first one at or after reference
    upcoming = [c for c in candidates if c >= reference]
    if upcoming:
        return min(upcoming)
    return max(candidates)


def find_next_dawn_after(observer, after: dt.datetime, tz: ZoneInfo, depression: float = 18) -> dt.datetime | None:
    """Find the first astronomical dawn that occurs strictly after 'after'."""
    base = after.date()
    for delta in range(0, 4):
        d = base + dt.timedelta(days=delta)
        try:
            val = dawn(observer, date=d, depression=depression).astimezone(tz)
            if val > after:
                return val
        except (ValueError, KeyError):
            continue
    return None


def moon_phase_name_and_illumination(phase_val: float) -> tuple[str, float]:
    """Return (name, percent_illuminated).

    astral.moon.phase() returns a value in [0, 28): 0=New, 7=First Quarter,
    14=Full, 21=Last Quarter. We bucket that 28-unit cycle into 8 named phases
    of 3.5 units each (the four principal phases centered on 0/7/14/21).
    """
    period = 28.0
    p = phase_val % period
    illum = (1 - math.cos(2 * math.pi * p / period)) / 2 * 100

    boundaries = [
        (0.00, 1.75, "New Moon"),
        (1.75, 5.25, "Waxing Crescent"),
        (5.25, 8.75, "First Quarter"),
        (8.75, 12.25, "Waxing Gibbous"),
        (12.25, 15.75, "Full Moon"),
        (15.75, 19.25, "Waning Gibbous"),
        (19.25, 22.75, "Last Quarter"),
        (22.75, 26.25, "Waning Crescent"),
    ]
    name = "New Moon"  # also covers the wrap-around tail [26.25, 28)
    for lo, hi, nm in boundaries:
        if p < hi:
            name = nm
            break
    return name, round(illum, 1)


def build_table(rows: list[tuple[str, str]]) -> str:
    """Simple clean fixed-width table."""
    if not rows:
        return ""
    label_w = max(len(r[0]) for r in rows)
    val_w = max(len(r[1]) for r in rows)
    line = "+" + "-" * (label_w + 2) + "+" + "-" * (val_w + 2) + "+"
    out = [line]
    for label, val in rows:
        out.append(f"| {label:<{label_w}} | {val:<{val_w}} |")
    out.append(line)
    return "\n".join(out)


def main():
    args = parse_args()

    # Resolve location and timezone
    lat = lon = city = region = tzname = None
    custom_location = False

    if args.lat is not None and args.lon is not None:
        lat, lon = args.lat, args.lon
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            print("Error: Latitude must be -90 to 90, longitude -180 to 180.")
            sys.exit(1)
        city, region = "", ""
        custom_location = True
        tzname = args.tzname or "UTC"
        if not args.tzname:
            print(
                "Warning: no --tz given for custom coordinates; defaulting to UTC. "
                "Use --tz to get times in the correct local civil time."
            )
    else:
        ip = get_location_from_ip()
        if ip:
            lat, lon, city, region, ip_tz = ip
            tzname = args.tzname or ip_tz
            if args.tzname:
                # User explicitly overrode the detected timezone
                print(f"Using provided timezone {args.tzname} (auto-detected: {city}, {region})")
            else:
                print(f"Auto-detected location: {city}, {region} (via IP)")
        else:
            print("Could not detect location via IP. Using fallback coordinates.")
            lat = FALLBACK["lat"]
            lon = FALLBACK["lon"]
            city = FALLBACK["city"]
            region = FALLBACK["region"]
            tzname = args.tzname or FALLBACK["tzname"]

    tz = ZoneInfo(tzname)
    observer = LocationInfo(city or "Location", region or "", tzname, lat, lon).observer

    # Determine reference time for "tonight"
    now = dt.datetime.now(tz)
    if args.date:
        try:
            target_date = dt.datetime.strptime(args.date, "%Y-%m-%d").date()
            reference = dt.datetime.combine(target_date, dt.time(12, 0), tzinfo=tz)
        except ValueError:
            print("Invalid --date format. Use YYYY-MM-DD.")
            sys.exit(1)
    else:
        reference = now
        target_date = reference.date()

    # Compute events using robust "best event relative to reference" logic.
    # This avoids date-crossing bugs when the display TZ does not match the longitude.
    sunset = find_best_event(observer, "sunset", reference, tz)

    if sunset is not None:
        # Anchor dusk search to the sunset time (or just after)
        dusk_ref = sunset
    else:
        dusk_ref = reference

    astro_dusk = find_best_event(observer, "dusk", dusk_ref, tz, 18.0)

    if astro_dusk is not None:
        astro_dawn = find_next_dawn_after(observer, astro_dusk, tz, 18.0)
    else:
        # Fallback: try to find any dawn after the reference
        astro_dawn = find_next_dawn_after(observer, dusk_ref, tz, 18.0)

    # For display purposes, prefer the calendar date of the actual sunset we picked
    display_date = sunset.date() if sunset is not None else target_date

    # Hours of darkness = astro_dusk → astro_dawn (only if both occur)
    if astro_dusk is not None and astro_dawn is not None:
        delta = astro_dawn - astro_dusk
        # Guard against obviously wrong multi-day spans (shouldn't happen with the new logic)
        if delta.total_seconds() > 60 * 60 * 30:  # > 30 hours is suspicious
            darkness_str = "calculation error (check coordinates/timezone)"
        else:
            secs = int(delta.total_seconds())
            darkness_str = f"{secs // 3600}h {(secs % 3600) // 60}m"
    else:
        darkness_str = "no astronomical darkness"

    # Moon phase at the display date
    mp = moon_phase(display_date)
    phase_name, illum_pct = moon_phase_name_and_illumination(mp)

    # Display header
    lat_str = f"{abs(lat):.4f}°{'N' if lat >= 0 else 'S'}"
    lon_str = f"{abs(lon):.4f}°{'E' if lon >= 0 else 'W'}"
    coord_str = f"{lat_str}, {lon_str}"
    night_label = display_date.strftime("%A, %B %d, %Y")

    print()
    if custom_location:
        print("Night Information — Custom location")
    elif city:
        loc_str = f"{city}, {region}".strip().rstrip(",")
        print(f"Night Information — {loc_str}")
    else:
        print("Night Information")
    print(f"Coordinates: {coord_str}")
    print(f"Timezone:    {tzname}")
    print(f"Night of:    {night_label}")
    print()

    # Table rows
    rows = [
        ("Sunset", fmt_time(sunset)),
        ("Astronomical twilight ends", fmt_time(astro_dusk)),
        ("Astronomical twilight begins", fmt_time(astro_dawn)),
        ("Moon phase", f"{phase_name} ({illum_pct}% illuminated)"),
        ("Hours of darkness", darkness_str),
    ]

    print(build_table(rows))
    print()


if __name__ == "__main__":
    main()
