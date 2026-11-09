"""Thin, safe wrapper around the ExifTool CLI.

Reads use `-j` (JSON) output for structured parsing. Writes use explicit
`-TAG=value` arguments (never a shell string) and `-overwrite_original`
only on a working copy that the caller controls — never on the user's
original upload.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from app.security.subprocess_exec import ExternalToolError, run_tool

EXIFTOOL_AVAILABLE = shutil.which("exiftool") is not None


class ExifToolUnavailable(ExternalToolError):
    pass


def _require() -> None:
    if not EXIFTOOL_AVAILABLE:
        raise ExifToolUnavailable("exiftool is not installed or not on PATH")


def read_all_tags(path: Path, timeout: int | None = None) -> dict[str, Any]:
    """Return the flat tag dict for a file (group names included), e.g.
    {"EXIF:Make": "Canon", "XMP:Creator": "..."}."""
    _require()
    result = run_tool(
        ["exiftool", "-j", "-G1", "-a", "-U", "-struct", "-api", "largefilesupport=1", str(path)],
        timeout=timeout,
    )
    if result.returncode not in (0, 1):  # exiftool returns 1 on warnings, still usable
        raise ExternalToolError(f"exiftool failed: {result.stderr_text[:500]}")
    try:
        data = json.loads(result.stdout_text or "[]")
    except json.JSONDecodeError as exc:
        raise ExternalToolError(f"exiftool produced invalid JSON: {exc}") from exc
    if not data:
        return {}
    return data[0]


def read_all_tags_with_ids(path: Path, timeout: int | None = None) -> dict[str, dict[str, Any]]:
    """Return the flat tag dict with real exiftool tag IDs attached, e.g.
    {"EXIF:Make": {"id": "0x010f", "val": "Canon"}, ...}.

    Combining `-H` (hex tag IDs) with `-struct` switches exiftool's JSON
    output to wrap every value as {"id": ..., "val": ...} instead of a bare
    value. For numeric IFD-style tags (EXIF/GPS/IFD0/IFD1) `id` is a real
    hex tag ID (e.g. "0x010f"); for text-keyed tags (XMP, composite/derived
    tags, filesystem pseudo-tags) `id` falls back to the tag name itself,
    since those namespaces are not numerically addressed in the file. This
    is exiftool's own documented behavior, not a heuristic we invented.
    """
    _require()
    result = run_tool(
        ["exiftool", "-j", "-G1", "-H", "-u", "-U", "-a", "-struct", "-api", "largefilesupport=1", str(path)],
        timeout=timeout,
    )
    if result.returncode not in (0, 1):
        raise ExternalToolError(f"exiftool failed: {result.stderr_text[:500]}")
    try:
        data = json.loads(result.stdout_text or "[]")
    except json.JSONDecodeError as exc:
        raise ExternalToolError(f"exiftool produced invalid JSON: {exc}") from exc
    if not data:
        return {}
    raw = data[0]
    out: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if isinstance(value, dict) and "val" in value:
            out[key] = {"id": value.get("id"), "val": value.get("val")}
        else:
            out[key] = {"id": None, "val": value}
    return out


def read_gps_decimal(path: Path, timeout: int | None = None) -> dict[str, float]:
    """Return GPS latitude/longitude/altitude as plain decimal numbers
    (exiftool's `-n` disables its human-readable DMS formatting), which is
    the only robust way to get a numeric decimal-degree value — parsing
    exiftool's own formatted DMS string back into a float is fragile and
    unnecessary when exiftool can just give us the number directly.
    """
    _require()
    result = run_tool(
        ["exiftool", "-j", "-n", "-GPSLatitude", "-GPSLongitude", "-GPSAltitude", str(path)],
        timeout=timeout,
    )
    if result.returncode not in (0, 1):
        return {}
    try:
        data = json.loads(result.stdout_text or "[]")
    except json.JSONDecodeError:
        return {}
    if not data:
        return {}
    row = data[0]
    out: dict[str, float] = {}
    for key in ("GPSLatitude", "GPSLongitude", "GPSAltitude"):
        val = row.get(key)
        if isinstance(val, (int, float)):
            out[key] = float(val)
    return out


def get_version() -> str | None:
    if not EXIFTOOL_AVAILABLE:
        return None
    try:
        result = run_tool(["exiftool", "-ver"], timeout=5)
        return result.stdout_text.strip() or None
    except Exception:
        return None


def write_tags(path: Path, tag_values: dict[str, str | None], timeout: int | None = None) -> tuple[bool, str]:
    """Write/remove tags on `path` IN PLACE (overwrite_original, no backup
    file left behind — caller must already be operating on a disposable
    working copy, never the original upload).

    tag_values: {"EXIF:Artist": "Jane Doe", "GPS:GPSLatitude": None, ...}
    A None value clears that tag. Returns (success, exiftool stderr/stdout tail).
    """
    _require()
    argv = ["exiftool", "-overwrite_original", "-P", "-m"]
    for tag, value in tag_values.items():
        if value is None:
            argv.append(f"-{tag}=")
        else:
            argv.append(f"-{tag}={value}")
    argv.append(str(path))
    result = run_tool(argv, timeout=timeout)
    ok = result.returncode == 0
    tail = (result.stdout_text + result.stderr_text).strip()[-800:]
    return ok, tail


def strip_all_writable(path: Path, keep_groups: list[str] | None = None, timeout: int | None = None) -> tuple[bool, str]:
    """Remove all metadata exiftool can write to, optionally keeping some
    groups (e.g. keep ICC profile)."""
    _require()
    # Selective-keep groups are handled by the editor layer (it restores
    # specific tags after this call using write_tags); this function always
    # performs the blanket "-all=" removal exiftool supports.
    argv = ["exiftool", "-overwrite_original", "-P", "-m", "-all="]
    argv.append(str(path))
    result = run_tool(argv, timeout=timeout)
    ok = result.returncode == 0
    tail = (result.stdout_text + result.stderr_text).strip()[-800:]
    return ok, tail
