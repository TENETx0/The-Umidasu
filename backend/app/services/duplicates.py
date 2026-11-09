"""Duplicate Metadata Detector — cross-references real extracted field
values against a curated map of "same real-world concept, different tag
namespace" groups (e.g. Artist / Creator / By-line all mean "author").
Flags groups where multiple namespaces carry a value as either
"redundant" (identical values — harmless duplication) or "conflicting"
(different values — a real inconsistency worth knowing about, e.g. the
file was edited by two tools that didn't stay in sync).

Matching is done on the bare tag name (the part after the LAST colon in
the field's key — e.g. "IFD0:Artist" -> "Artist", "ExifIFD:DateTimeOriginal"
-> "DateTimeOriginal", "XMP-dc:Creator" -> "Creator", "core:author" ->
"author"), because exiftool's `-G1` grouping uses specific IFD/namespace
names (IFD0, ExifIFD, XMP-dc, XMP-tiff, ...) rather than flat family names,
so matching on full "EXIF:Tag"-style keys would silently never match. Bare
tag names are case-sensitive on purpose: IPTC/EXIF tags are PascalCase
("Keywords") while Office/PDF logical keys are lower_snake ("keywords"),
and both spellings are listed explicitly below where both exist.

This performs no fabrication: every value compared is a value this
session already extracted from the file via exiftool/PyMuPDF/python-docx.
"""
from __future__ import annotations

from app.models.schemas import DuplicateGroup, MetadataField

# concept -> candidate bare tag names representing it across namespaces
_CONCEPT_TAG_NAMES: dict[str, list[str]] = {
    "Author / Creator": ["Artist", "Creator", "By-line", "Author", "OwnerName", "CameraOwnerName", "author"],
    "Copyright": ["Copyright", "Rights", "CopyrightNotice"],
    "Creation Date": ["DateTimeOriginal", "CreateDate", "DateCreated", "created", "creationDate"],
    "Modification Date": ["ModifyDate", "modified", "modDate"],
    "Description / Caption": ["ImageDescription", "Description", "Caption-Abstract", "comments"],
    "Title": ["Title", "ObjectName", "title"],
    "Keywords": ["Keywords", "Subject", "keywords"],
    "Software / Tool": ["Software", "CreatorTool", "producer", "creator"],
}


def _normalize_for_compare(value) -> str:
    return str(value).strip().lower() if value is not None else ""


def _bare_tag_name(key: str) -> str:
    return key.split(":", 1)[-1] if ":" in key else key


def detect_duplicates(sections) -> list[DuplicateGroup]:
    fields_by_tag_name: dict[str, list[MetadataField]] = {}
    for section in sections:
        for f in section.fields:
            fields_by_tag_name.setdefault(_bare_tag_name(f.key), []).append(f)

    groups: list[DuplicateGroup] = []
    for concept, tag_names in _CONCEPT_TAG_NAMES.items():
        present: list[MetadataField] = []
        seen_keys: set[str] = set()
        for name in tag_names:
            for f in fields_by_tag_name.get(name, []):
                if f.key in seen_keys:
                    continue
                if f.normalized_value in (None, ""):
                    continue
                # Skip derived/composite duplicates of the same underlying
                # value (e.g. Composite:GPSLatitude vs GPS:GPSLatitude) —
                # those aren't independent namespaces, just display forms.
                if f.namespace == "Composite":
                    continue
                present.append(f)
                seen_keys.add(f.key)
        if len(present) < 2:
            continue
        normalized_values = {_normalize_for_compare(f.normalized_value) for f in present}
        status = "redundant" if len(normalized_values) == 1 else "conflicting"
        groups.append(DuplicateGroup(
            concept=concept,
            status=status,
            fields=[{"key": f.key, "label": f.label, "value": f.normalized_value} for f in present],
        ))
    return groups
