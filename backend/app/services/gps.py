"""GPS Coordinate Converter — decimal degrees <-> DMS <-> DDM.

All conversions are pure arithmetic from a single decimal-degree source of
truth (obtained directly from exiftool's `-n` numeric output, never by
re-parsing exiftool's own human-formatted DMS string), so there is no
precision loss or fragile string parsing involved.
"""
from __future__ import annotations

import math


def decimal_to_dms(decimal_deg: float) -> tuple[int, int, float]:
    """Return (degrees, minutes, seconds) — all non-negative; the caller
    tracks sign/hemisphere separately."""
    value = abs(decimal_deg)
    degrees = int(value)
    remainder = (value - degrees) * 60
    minutes = int(remainder)
    seconds = (remainder - minutes) * 60
    return degrees, minutes, round(seconds, 3)


def decimal_to_ddm(decimal_deg: float) -> tuple[int, float]:
    """Return (degrees, decimal_minutes)."""
    value = abs(decimal_deg)
    degrees = int(value)
    minutes = (value - degrees) * 60
    return degrees, round(minutes, 5)


def format_dms(decimal_deg: float, is_lat: bool) -> str:
    d, m, s = decimal_to_dms(decimal_deg)
    hemi = ("N" if decimal_deg >= 0 else "S") if is_lat else ("E" if decimal_deg >= 0 else "W")
    return f"{d}°{m}'{s:.2f}\" {hemi}"


def format_ddm(decimal_deg: float, is_lat: bool) -> str:
    d, m = decimal_to_ddm(decimal_deg)
    hemi = ("N" if decimal_deg >= 0 else "S") if is_lat else ("E" if decimal_deg >= 0 else "W")
    return f"{d}° {m:.4f}' {hemi}"


def format_decimal(decimal_deg: float, is_lat: bool) -> str:
    hemi = ("N" if decimal_deg >= 0 else "S") if is_lat else ("E" if decimal_deg >= 0 else "W")
    return f"{abs(decimal_deg):.6f}° {hemi} ({decimal_deg:+.6f})"


def maidenhead_locator(lat: float, lon: float, precision: int = 3) -> str | None:
    """Maidenhead grid locator — a compact amateur-radio-style geocode,
    offered as an additional "common representation". Returns None for
    out-of-range coordinates."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    lon_adj = lon + 180
    lat_adj = lat + 90
    A = "ABCDEFGHIJKLMNOPQRSTUVWX"
    field_lon = int(lon_adj / 20)
    field_lat = int(lat_adj / 10)
    locator = A[field_lon] + A[field_lat]
    lon_rem = lon_adj - field_lon * 20
    lat_rem = lat_adj - field_lat * 10
    square_lon = int(lon_rem / 2)
    square_lat = int(lat_rem / 1)
    locator += f"{square_lon}{square_lat}"
    if precision >= 3:
        lon_rem2 = (lon_rem - square_lon * 2) * 60 / 5
        lat_rem2 = (lat_rem - square_lat * 1) * 60 / 2.5
        subsq = "abcdefghijklmnopqrstuvwx"
        locator += subsq[int(lon_rem2)] + subsq[int(lat_rem2)]
    return locator


def build_representations(lat: float | None, lon: float | None) -> dict[str, dict[str, str]]:
    """Build the full set of alternate representations for a GPS fix.
    Returns {"latitude": {...}, "longitude": {...}} — each with decimal,
    dms, and ddm strings — plus a combined Maidenhead locator when both
    coordinates are available."""
    out: dict[str, dict[str, str]] = {}
    if lat is not None:
        out["latitude"] = {
            "decimal": format_decimal(lat, is_lat=True),
            "dms": format_dms(lat, is_lat=True),
            "ddm": format_ddm(lat, is_lat=True),
            "raw_decimal": f"{lat:.8f}",
        }
    if lon is not None:
        out["longitude"] = {
            "decimal": format_decimal(lon, is_lat=False),
            "dms": format_dms(lon, is_lat=False),
            "ddm": format_ddm(lon, is_lat=False),
            "raw_decimal": f"{lon:.8f}",
        }
    if lat is not None and lon is not None:
        locator = maidenhead_locator(lat, lon)
        if locator:
            out["grid_locator"] = {"maidenhead": locator}
    return out


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in kilometers — useful
    when comparing GPS fixes across files (e.g. via Copy & Paste)."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
