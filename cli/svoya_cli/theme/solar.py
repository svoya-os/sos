"""Sunrise and sunset — the NOAA solar calculator algorithm (Meeus-based, ±1 min at mid latitudes).

Reference: NOAA Global Monitoring Laboratory, "General Solar Position Calculations" and the
NOAA solar calculator spreadsheet. Sunrise/sunset use the standard zenith 90.833° (refraction +
solar disc radius). Times are returned in UTC; polar day/night are reported explicitly.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

ZENITH = 90.833


@dataclass
class SunTimes:
    sunrise: dt.datetime | None   # UTC
    sunset: dt.datetime | None    # UTC
    noon: dt.datetime             # UTC
    polar: str | None = None      # "day" (midnight sun) | "night" (polar night) | None


def _julian_day(d: dt.date) -> float:
    """Julian day at 0h UTC of the date."""
    return dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp() / 86400.0 + 2440587.5


def _sun(jd: float) -> tuple[float, float]:
    """Solar declination (deg) and equation of time (minutes) at Julian day ``jd``."""
    t = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    mr = math.radians(m)
    c = (math.sin(mr) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + math.sin(2 * mr) * (0.019993 - 0.000101 * t)
         + math.sin(3 * mr) * 0.000289)
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    eps0 = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))
    decl = math.degrees(math.asin(math.sin(math.radians(eps)) * math.sin(math.radians(app_long))))
    y = math.tan(math.radians(eps / 2)) ** 2
    l0r = math.radians(l0)
    eqt = 4 * math.degrees(
        y * math.sin(2 * l0r) - 2 * e * math.sin(mr) + 4 * e * y * math.sin(mr) * math.cos(2 * l0r)
        - 0.5 * y * y * math.sin(4 * l0r) - 1.25 * e * e * math.sin(2 * mr))
    return decl, eqt


def _hour_angle(lat: float, decl: float) -> float | None:
    """Sunrise hour angle (deg); None when the sun does not cross the horizon."""
    la, de = math.radians(lat), math.radians(decl)
    x = math.cos(math.radians(ZENITH)) / (math.cos(la) * math.cos(de)) - math.tan(la) * math.tan(de)
    if x > 1 or x < -1:
        return None
    return math.degrees(math.acos(x))


def sun_times(date: dt.date, lat: float, lon: float) -> SunTimes:
    """Sunrise/sunset (UTC) for a calendar date at a location (lon east positive)."""
    jd0 = _julian_day(date)
    midnight = dt.datetime(date.year, date.month, date.day, tzinfo=dt.timezone.utc)

    def at(minutes: float) -> dt.datetime:
        return midnight + dt.timedelta(minutes=minutes)

    # solar noon, refined twice with the sun position at that moment
    noon_min = 720 - 4 * lon
    for _ in range(2):
        decl, eqt = _sun(jd0 + noon_min / 1440)
        noon_min = 720 - 4 * lon - eqt
    decl, eqt = _sun(jd0 + noon_min / 1440)
    ha = _hour_angle(lat, decl)
    if ha is None:
        # sun above the horizon all day when latitude and declination share a sign
        polar = "day" if (lat >= 0) == (decl >= 0) else "night"
        return SunTimes(None, None, at(noon_min), polar)

    def event(sign: int) -> float:
        t = noon_min + sign * 4 * ha
        for _ in range(2):  # re-evaluate the sun at the event time itself
            d, q = _sun(jd0 + t / 1440)
            h = _hour_angle(lat, d)
            if h is None:
                break
            t = 720 - 4 * lon - q + sign * 4 * h
        return t

    return SunTimes(at(event(-1)), at(event(+1)), at(noon_min))


def is_daytime(now: dt.datetime, lat: float, lon: float,
               fallback: tuple[int, int] = (7, 20)) -> tuple[bool, str]:
    """True between sunrise and sunset. Polar day/night and bad input fall back to the fixed
    local schedule 07:00–20:00 (a daily rhythm beats two months of one theme)."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    local = now.astimezone()
    try:
        if not (-90 <= float(lat) <= 90 and -180 <= float(lon) <= 180):
            raise ValueError("bad coordinates")
        st = sun_times(local.date(), float(lat), float(lon))
        if st.sunrise and st.sunset:
            return st.sunrise <= now < st.sunset, "sun"
        reason = f"polar-{st.polar}"
    except (TypeError, ValueError):
        reason = "invalid-location"
    start, end = fallback
    return start <= local.hour < end, f"fallback ({reason})"
