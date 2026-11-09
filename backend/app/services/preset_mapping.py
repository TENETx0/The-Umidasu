"""Metadata Presets — maps a small set of user-facing "logical" fields
(author, copyright, title, description, keywords) onto the concrete,
format-specific tag keys each metadata domain actually supports, so one
saved preset can be sensibly applied to an image, a PDF, or an Office
document alike. Fields with no sensible analog in a given domain are
reported as skipped rather than silently dropped or force-mapped onto an
unrelated tag.

Write keys deliberately use the SAME specific-group names (IFD0/ExifIFD/
XMP-dc/IPTC) that a `-G1` read reports, rather than exiftool's more
permissive family-0 group names (e.g. "EXIF:Artist"). exiftool accepts
either as a write target — verified: `exiftool -EXIF:Artist=X file.jpg`
writes correctly and is later read back as `IFD0:Artist` under `-G1` — but
using the family-0 form here would make a staged pending edit carry a
*different* key than the one the analysis/diff/snapshot machinery reads
the field back under. That mismatch doesn't break the write itself, but it
does make Metadata Difference Highlighting show the change as a brand-new
field ("EXIF:Artist" added) instead of a modification of the existing one
("IFD0:Artist" changed), and makes a snapshot restore's diff miss it
entirely. Keeping both sides on the same key avoids that class of bug —
see domains.py for the read-side matching rationale.
"""
from __future__ import annotations

_MAPPING: dict[str, dict[str, list[str]]] = {
    "author": {
        "image_media": ["IFD0:Artist", "XMP-dc:Creator"],
        "office": ["core:author"],
        "pdf": ["pdf:author"],
    },
    "copyright": {
        "image_media": ["IFD0:Copyright", "XMP-dc:Rights"],
        "office": [],
        "pdf": [],
    },
    "title": {
        "image_media": ["XMP-dc:Title"],
        "office": ["core:title"],
        "pdf": ["pdf:title"],
    },
    "description": {
        "image_media": ["IFD0:ImageDescription", "XMP-dc:Description"],
        "office": ["core:comments"],
        "pdf": [],
    },
    "keywords": {
        "image_media": ["IPTC:Keywords", "XMP-dc:Subject"],
        "office": ["core:keywords"],
        "pdf": ["pdf:keywords"],
    },
}

LOGICAL_FIELDS = list(_MAPPING.keys())


def concrete_keys_for(logical_name: str, domain: str) -> list[str]:
    return _MAPPING.get(logical_name, {}).get(domain, [])
