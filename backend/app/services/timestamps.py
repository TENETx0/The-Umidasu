"""Timestamp Normalizer — detects exiftool-style date/time strings and,
only when the source value carries an explicit UTC offset, computes a true
UTC equivalent. When no offset is present (the common case for EXIF, which
does not mandate a timezone), we do NOT silently assume one — EXIF/IPTC/XMP
timestamps without an offset are fundamentally ambiguous, and presenting a
fabricated "UTC" conversion would be dishonest. Instead we flag
`timestamp_has_tz=False` and leave the timezone assumption to the user
(the frontend offers an explicit, clearly-labeled "interpret as" control
that never mutates the stored value).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

# exiftool date format: "YYYY:MM:DD HH:MM:SS" optionally followed by a
# fractional-seconds part and/or a timezone offset ("+05:30", "-08:00", "Z").
_EXIFTOOL_DATE_RE = re.compile(
    r"^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$"
)


def looks_like_timestamp(value: object) -> bool:
    return isinstance(value, str) and bool(_EXIFTOOL_DATE_RE.match(value.strip()))


def parse_exiftool_timestamp(value: str) -> tuple[str | None, bool]:
    """Returns (utc_iso_or_None, has_tz). utc_iso is only populated when the
    source string carried an explicit offset."""
    m = _EXIFTOOL_DATE_RE.match(value.strip())
    if not m:
        return None, False
    year, month, day, hour, minute, second, _frac, offset = m.groups()
    if not offset:
        return None, False

    iso_naive = f"{year}-{month}-{day}T{hour}:{minute}:{second}"
    if offset == "Z":
        iso = iso_naive + "+00:00"
    else:
        off = offset if ":" in offset else f"{offset[:3]}:{offset[3:]}"
        iso = iso_naive + off
    try:
        dt = datetime.fromisoformat(iso)
        return dt.astimezone(timezone.utc).isoformat(), True
    except ValueError:
        return None, False


def try_generic_iso(value: str) -> tuple[str | None, bool]:
    """Fallback for non-exiftool-formatted timestamps this app also
    surfaces (ffprobe's ISO-8601 `creation_time` tag, python-docx/openpyxl/
    python-pptx core-property datetimes already rendered as strings like
    '2013-12-23 23:15:00+00:00'). Returns (utc_iso_or_None, has_tz)."""
    v = value.strip()
    if len(v) < 10 or v[4] != "-":
        return None, False  # cheap pre-filter before attempting a parse
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None, False
    if dt.tzinfo is None:
        return None, False
    return dt.astimezone(timezone.utc).isoformat(), True


def detect_and_annotate(value: object) -> tuple[bool, str | None, str | None, bool]:
    """Single entry point used by the analysis post-processing pass.
    Returns (is_timestamp, forced_value_type_or_None, timestamp_utc, timestamp_has_tz)."""
    if not isinstance(value, str):
        return False, None, None, False
    if looks_like_timestamp(value):
        utc, has_tz = parse_exiftool_timestamp(value)
        return True, "date", utc, has_tz
    utc, has_tz = try_generic_iso(value)
    if has_tz:
        return True, "date", utc, has_tz
    return False, None, None, False


FIXED_OFFSET_CHOICES = [
    ("UTC-12:00", -12 * 60), ("UTC-11:00", -11 * 60), ("UTC-10:00", -10 * 60),
    ("UTC-09:00", -9 * 60), ("UTC-08:00", -8 * 60), ("UTC-07:00", -7 * 60),
    ("UTC-06:00", -6 * 60), ("UTC-05:00", -5 * 60), ("UTC-04:00", -4 * 60),
    ("UTC-03:00", -3 * 60), ("UTC-02:00", -2 * 60), ("UTC-01:00", -1 * 60),
    ("UTC+00:00", 0), ("UTC+01:00", 60), ("UTC+02:00", 120), ("UTC+03:00", 180),
    ("UTC+04:00", 240), ("UTC+05:00", 300), ("UTC+05:30", 330), ("UTC+06:00", 360),
    ("UTC+07:00", 420), ("UTC+08:00", 480), ("UTC+09:00", 540), ("UTC+09:30", 570),
    ("UTC+10:00", 600), ("UTC+12:00", 720), ("UTC+13:00", 780),
]
