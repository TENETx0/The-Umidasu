"""Shared "metadata domain" compatibility logic for Copy & Paste and
Presets. A domain is the broad category of writable metadata a file
format exposes (image/media tags via exiftool, Office core properties,
PDF /Info dictionary). Two files are compatible for a field transfer when
they share a domain — transplanting an EXIF tag onto a PDF, or a PDF
/Info key onto a spreadsheet, is meaningless and is refused.
"""
from __future__ import annotations

from app.services.exiftool_service import EXIFTOOL_AVAILABLE

IMAGE_MEDIA_SECTION_IDS = {
    "exif", "gps", "camera", "author", "iptc", "xmp", "icc", "image_technical", "unknown_tags",
    "media_container", "media_video_streams", "media_audio_streams", "media_tags", "media_other_streams",
}
OFFICE_SECTION_IDS = {"office_core", "office_structure"}
PDF_SECTION_IDS = {"pdf_document", "pdf_structure"}


def domain_for_analysis(section_ids: set[str]) -> str | None:
    if section_ids & OFFICE_SECTION_IDS:
        return "office"
    if section_ids & PDF_SECTION_IDS:
        return "pdf"
    if section_ids & IMAGE_MEDIA_SECTION_IDS:
        return "image_media"
    return None


def domain_for_key(key: str) -> str | None:
    """Infer which domain a specific metadata key belongs to, from its own
    key prefix convention (consistent across this codebase's parsers)."""
    if key.startswith("core:"):
        return "office"
    if key.startswith("pdf:"):
        return "pdf"
    if key.startswith(("struct:", "zip:", "bin:", "format:", "stream")):
        return None  # structural/read-only, never a transfer candidate
    if ":" in key:
        return "image_media"  # exiftool-style GROUP:Tag key
    return None


def is_compatible(source_key: str, target_section_ids: set[str]) -> tuple[bool, str | None]:
    """Return (compatible, reason_if_not)."""
    key_domain = domain_for_key(source_key)
    if key_domain is None:
        return False, "This field is structural/read-only and cannot be transferred."

    target_domain = domain_for_analysis(target_section_ids)
    if target_domain is None:
        return False, "The target file's format does not expose any writable metadata domain."

    if key_domain != target_domain:
        label = {"office": "an Office document", "pdf": "a PDF", "image_media": "an image/video/audio file"}
        return False, f"This field belongs to {label.get(key_domain, key_domain)}; the target is not {label.get(target_domain, target_domain)}."

    if key_domain == "image_media" and not EXIFTOOL_AVAILABLE:
        return False, "exiftool is not installed, so image/media tags cannot be written."

    return True, None
