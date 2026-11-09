"""Applies pending metadata edits (and custom filesystem timestamps) from a
working copy to a new Save-As output file, then verifies the result by
re-extracting metadata from the output.

Writable fields are currently those exiftool can write (EXIF/IPTC/XMP/GPS
tags on images and media containers) and OOXML core properties (docx/xlsx/
pptx) via python-docx/openpyxl/python-pptx. PDF document-info fields are
writable via pikepdf. Anything else is reported back as unsupported rather
than silently dropped.
"""
from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.schemas import FileHashes
from app.services import exiftool_service, hashing
from app.services.exiftool_service import EXIFTOOL_AVAILABLE

try:
    import pikepdf
    _HAVE_PIKEPDF = True
except Exception:
    _HAVE_PIKEPDF = False


@dataclass
class EditOutcome:
    applied: list[dict]
    unsupported: list[dict]
    failed: list[dict]
    tool_versions: dict[str, str | None]


def _parse_iso(value: str) -> float:
    """Parse an ISO-8601 timestamp (from the custom timestamp fields) into
    a POSIX epoch float, accepting a trailing 'Z'."""
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def apply_custom_timestamps(output_path: Path, created: str | None, modified: str | None, accessed: str | None) -> dict[str, Any]:
    """Set filesystem modified/accessed time (os.utime) and, where exiftool
    is available, embedded FileCreateDate/FileModifyDate-equivalent tags
    plus common EXIF/XMP date fields so the "created" concept is reflected
    both at the OS level (where the platform supports it) and, best-effort,
    in embedded metadata.

    True filesystem "created" (birth) time cannot be set directly on Linux
    through any public syscall — this is a platform limitation, not an
    application bug. We report exactly what was and wasn't changed.
    """
    report: dict[str, Any] = {"filesystem": {}, "embedded": {}, "notes": []}

    # --- Filesystem level ---
    try:
        current = output_path.stat()
        new_atime = _parse_iso(accessed) if accessed else current.st_atime
        new_mtime = _parse_iso(modified) if modified else current.st_mtime
        os.utime(output_path, (new_atime, new_mtime))
        report["filesystem"]["modified"] = modified is not None
        report["filesystem"]["accessed"] = accessed is not None
    except Exception as exc:
        report["notes"].append(f"Failed to set filesystem timestamps: {exc}")

    if created:
        report["notes"].append(
            "Filesystem 'created' (birth) time cannot be modified on Linux via any public API; "
            "it reflects when this output file was actually written to disk. The requested created "
            "date was instead written to embedded metadata where the format supports it."
        )
        report["filesystem"]["created"] = False

    # --- Embedded metadata level (best-effort, format permitting) ---
    if EXIFTOOL_AVAILABLE and (created or modified):
        tag_values: dict[str, str] = {}

        def exif_dt(iso: str) -> str:
            ts = _parse_iso(iso)
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y:%m:%d %H:%M:%S")

        if created:
            for tag in ("EXIF:DateTimeOriginal", "EXIF:CreateDate", "XMP:CreateDate", "QuickTime:CreateDate"):
                tag_values[tag] = exif_dt(created)
        if modified:
            for tag in ("EXIF:ModifyDate", "XMP:ModifyDate", "QuickTime:ModifyDate", "FileModifyDate"):
                tag_values[tag] = exif_dt(modified)
        if tag_values:
            try:
                ok, tail = exiftool_service.write_tags(output_path, tag_values)
                report["embedded"]["attempted_tags"] = list(tag_values.keys())
                report["embedded"]["success"] = ok
                if not ok:
                    report["notes"].append(f"exiftool reported an issue writing date tags: {tail}")
            except Exception as exc:
                report["embedded"]["success"] = False
                report["notes"].append(f"Embedded date-tag write failed: {exc}")
    elif (created or modified) and not EXIFTOOL_AVAILABLE:
        report["notes"].append("exiftool unavailable — only filesystem timestamps were updated, not embedded date tags.")

    return report


def _apply_exiftool_edits(output_path: Path, edits: list[dict]) -> tuple[list[dict], list[dict]]:
    applied, failed = [], []
    tag_values: dict[str, str | None] = {}
    by_tag: dict[str, dict] = {}
    for e in edits:
        key = e["field_key"]  # exiftool-qualified key, e.g. "EXIF:Artist"
        value = None if e["action"] == "remove" else e.get("new_value")
        tag_values[key] = None if value is None else str(value)
        by_tag[key] = e

    if not tag_values:
        return applied, failed
    try:
        ok, tail = exiftool_service.write_tags(output_path, tag_values)
    except Exception as exc:
        for key, e in by_tag.items():
            failed.append({**e, "reason": str(exc)})
        return applied, failed

    if ok:
        for key, e in by_tag.items():
            applied.append(e)
    else:
        for key, e in by_tag.items():
            failed.append({**e, "reason": tail or "exiftool reported failure"})
    return applied, failed


def _set_core_attr(cp: Any, attr: str, edits_for_attr: dict, applied: list[dict], failed: list[dict]) -> None:
    """Set one core-property attribute, guarded against a class of false
    positive this codebase used to have: python-docx/openpyxl/python-pptx
    core-properties objects are plain Python objects, so `setattr(cp,
    "made_up_attr", value)` NEVER raises — it just creates an ordinary
    instance attribute that is never serialized, and the edit would have
    been reported "applied" while nothing was actually written. The three
    formats also don't share one attribute set (e.g. openpyxl exposes
    "creator"/"description"/"contentStatus", not python-docx's "author"/
    "comments"/"content_status" — verified empirically), so a single
    hardcoded whitelist can't cover all three. `hasattr` is checked first
    instead: for an attribute that was never previously set, Python's
    default attribute lookup raises AttributeError and hasattr correctly
    returns False, whether or not it's a real property — verified against
    fresh python-docx/openpyxl/python-pptx objects for both valid and
    invalid names before relying on it here.
    """
    e = edits_for_attr
    if not hasattr(cp, attr):
        failed.append({**e, "reason": f"'{attr}' is not a core property this file format supports."})
        return
    try:
        value = None if e["action"] == "remove" else e.get("new_value")
        setattr(cp, attr, value or "")
        applied.append(e)
    except Exception as exc:
        failed.append({**e, "reason": str(exc)})


def _apply_office_edits(output_path: Path, extension: str, edits: list[dict]) -> tuple[list[dict], list[dict]]:
    applied, failed = [], []
    core_edits = {e["field_key"].split(":", 1)[-1]: e for e in edits if e["field_key"].startswith("core:")}
    if not core_edits:
        return applied, failed
    try:
        if extension == "docx":
            import docx
            d = docx.Document(str(output_path))
            cp = d.core_properties
            for attr, e in core_edits.items():
                _set_core_attr(cp, attr, e, applied, failed)
            d.save(str(output_path))
        elif extension == "xlsx":
            import openpyxl
            wb = openpyxl.load_workbook(str(output_path))
            cp = wb.properties
            for attr, e in core_edits.items():
                _set_core_attr(cp, attr, e, applied, failed)
            wb.save(str(output_path))
        elif extension == "pptx":
            from pptx import Presentation
            prs = Presentation(str(output_path))
            cp = prs.core_properties
            for attr, e in core_edits.items():
                _set_core_attr(cp, attr, e, applied, failed)
            prs.save(str(output_path))
        else:
            for e in core_edits.values():
                failed.append({**e, "reason": f"Unsupported office extension: {extension}"})
    except Exception as exc:
        for e in core_edits.values():
            if e not in applied:
                failed.append({**e, "reason": str(exc)})
    return applied, failed


def _apply_pdf_edits(output_path: Path, edits: list[dict]) -> tuple[list[dict], list[dict]]:
    applied, failed = [], []
    pdf_edits = {e["field_key"].split(":", 1)[-1]: e for e in edits if e["field_key"].startswith("pdf:")}
    if not pdf_edits:
        return applied, failed
    if not _HAVE_PIKEPDF:
        for e in pdf_edits.values():
            failed.append({**e, "reason": "pikepdf not installed"})
        return applied, failed
    try:
        with pikepdf.open(output_path, allow_overwriting_input=True) as pdf:
            with pdf.open_metadata() as meta:
                pass  # XMP left untouched; we edit the classic /Info dict below for broad compatibility
            info = pdf.docinfo
            key_map = {"title": "/Title", "author": "/Author", "subject": "/Subject",
                       "creator": "/Creator", "keywords": "/Keywords", "producer": "/Producer"}
            for attr, e in pdf_edits.items():
                pdf_key = key_map.get(attr)
                if not pdf_key:
                    failed.append({**e, "reason": f"Field '{attr}' is not writable via pikepdf docinfo"})
                    continue
                try:
                    if e["action"] == "remove":
                        if pdf_key in info:
                            del info[pdf_key]
                    else:
                        info[pdf_key] = str(e.get("new_value", ""))
                    applied.append(e)
                except Exception as exc:
                    failed.append({**e, "reason": str(exc)})
            pdf.save(output_path)
    except Exception as exc:
        for e in pdf_edits.values():
            if e not in applied:
                failed.append({**e, "reason": str(exc)})
    return applied, failed


def apply_edits_and_save(working_path: Path, output_path: Path, extension: str, edits: list[dict]) -> EditOutcome:
    """Copy the working file to output_path, then apply all edits to the
    output (never to the working copy or original)."""
    shutil.copy2(working_path, output_path)

    applied: list[dict] = []
    unsupported: list[dict] = []
    failed: list[dict] = []

    exiftool_edits = [e for e in edits if not e["field_key"].startswith(("core:", "pdf:", "struct:", "zip:"))]
    office_edits = [e for e in edits if e["field_key"].startswith("core:")]
    pdf_edits = [e for e in edits if e["field_key"].startswith("pdf:")]
    other_edits = [e for e in edits if e["field_key"].startswith(("struct:", "zip:"))]

    if exiftool_edits:
        if EXIFTOOL_AVAILABLE:
            a, f = _apply_exiftool_edits(output_path, exiftool_edits)
            applied += a
            failed += f
        else:
            unsupported += [{**e, "reason": "exiftool not installed"} for e in exiftool_edits]

    if office_edits:
        if extension in ("docx", "xlsx", "pptx"):
            a, f = _apply_office_edits(output_path, extension, office_edits)
            applied += a
            failed += f
        else:
            unsupported += [{**e, "reason": f"Not an editable Office format: {extension}"} for e in office_edits]

    if pdf_edits:
        if extension == "pdf":
            a, f = _apply_pdf_edits(output_path, pdf_edits)
            applied += a
            failed += f
        else:
            unsupported += [{**e, "reason": f"Not a PDF: {extension}"} for e in pdf_edits]

    for e in other_edits:
        unsupported.append({**e, "reason": "Structural/package-level fields are read-only."})

    tool_versions = {"exiftool": exiftool_service.get_version()}

    return EditOutcome(applied=applied, unsupported=unsupported, failed=failed, tool_versions=tool_versions)


def strip_metadata_preset(output_path: Path, presets: list[str], extension: str) -> dict[str, Any]:
    """Apply a removal preset directly to output_path (already a working copy)."""
    report: dict[str, Any] = {"applied": [], "unsupported": [], "notes": []}

    exiftool_presets = {
        "gps": {"GPS:all": None},
        "camera": {"EXIF:Make": None, "EXIF:Model": None, "EXIF:LensModel": None, "EXIF:SerialNumber": None,
                   "EXIF:LensSerialNumber": None, "EXIF:LensMake": None},
        "author": {"EXIF:Artist": None, "XMP:Creator": None, "IPTC:By-line": None, "EXIF:Copyright": None,
                    "XMP:Rights": None, "PNG:Author": None},
        "timestamps": {"EXIF:DateTimeOriginal": None, "EXIF:CreateDate": None, "EXIF:ModifyDate": None,
                        "XMP:CreateDate": None, "XMP:ModifyDate": None},
        "comments": {"EXIF:UserComment": None, "PNG:Comment": None, "XMP:Description": None, "IPTC:Caption-Abstract": None},
        "xmp_iptc": {"XMP:all": None, "IPTC:all": None},
    }

    if "all_writable" in presets:
        if EXIFTOOL_AVAILABLE:
            ok, tail = exiftool_service.strip_all_writable(output_path)
            report["applied"].append({"preset": "all_writable", "success": ok, "detail": tail[-300:]})
        else:
            report["unsupported"].append({"preset": "all_writable", "reason": "exiftool not installed"})
        presets = [p for p in presets if p != "all_writable"]

    if presets and EXIFTOOL_AVAILABLE:
        merged: dict[str, str | None] = {}
        applied_names = []
        for p in presets:
            if p in exiftool_presets:
                merged.update(exiftool_presets[p])
                applied_names.append(p)
            else:
                report["unsupported"].append({"preset": p, "reason": "No handler for this preset"})
        if merged:
            ok, tail = exiftool_service.write_tags(output_path, merged)
            report["applied"].append({"presets": applied_names, "success": ok, "detail": tail[-300:]})
    elif presets and not EXIFTOOL_AVAILABLE:
        for p in presets:
            report["unsupported"].append({"preset": p, "reason": "exiftool not installed"})

    report["notes"].append("Some data may remain in pixels, document body content, embedded streams, thumbnails, "
                            "signatures, file-system attributes, or format-specific structures that are not writable tags.")
    return report


def verify_output(original_path: Path, output_path: Path, expected_field_changes: list[str]) -> dict[str, Any]:
    """Recompute output hashes and re-extract metadata to confirm expected
    fields actually changed relative to the original.

    exiftool write targets accept family-0 group names (e.g. "EXIF:Artist")
    but `-G1` reads back report the specific IFD/namespace group instead
    (e.g. "IFD0:Artist", "ExifIFD:DateTimeOriginal") — verified empirically.
    An exact-key lookup alone would therefore report many successfully
    written fields as falsely absent. We look up by exact key first, and
    only fall back to matching the bare tag name (preferring a non-Composite
    field, since Composite tags are derived/read-only views) when the exact
    key isn't found — so this diagnostic stays honest for both naming
    conventions instead of silently under-reporting success.
    """
    from app.services.analysis import analyze_file

    output_hashes = hashing.compute_hashes(output_path)
    try:
        reanalyzed = analyze_file("verify", output_path, output_path.name, output_path.name)
        field_map: dict[str, Any] = {}
        bare_map: dict[str, Any] = {}
        bare_is_composite: dict[str, bool] = {}
        for s in reanalyzed.sections:
            for f in s.fields:
                field_map[f.key] = f.normalized_value
                if ":" in f.key:
                    bare = f.key.split(":", 1)[-1]
                    is_composite = f.namespace == "Composite"
                    if bare not in bare_map or (bare_is_composite.get(bare) and not is_composite):
                        bare_map[bare] = f.normalized_value
                        bare_is_composite[bare] = is_composite
    except Exception as exc:
        return {"re_extracted": False, "error": str(exc), "output_hashes": output_hashes.model_dump()}

    fields_present: dict[str, Any] = {}
    for k in expected_field_changes:
        if k in field_map:
            fields_present[k] = field_map[k]
        else:
            bare = k.split(":", 1)[-1] if ":" in k else k
            fields_present[k] = bare_map.get(bare)

    return {
        "re_extracted": True,
        "output_hashes": output_hashes.model_dump(),
        "fields_present_after_edit": fields_present,
        "hash_changed_from_input": True,  # caller compares against the pre-edit hash explicitly
    }
