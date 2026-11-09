"""Missing Metadata Suggestions — flags commonly-populated fields that are
absent from this specific file, phrased neutrally. This is informational,
not a defect report: plenty of legitimate files simply never had these
fields set (e.g. a screenshot has no "author", a scanned PDF has no XMP).

Candidate keys list bare tag names (matched against the part of each
field's key after its LAST colon) because exiftool's `-G1` grouping uses
specific namespace names (IFD0, ExifIFD, XMP-dc, ...) rather than a flat
"EXIF:"/"XMP:" prefix — see duplicates.py for the same rationale.
"""
from __future__ import annotations

from app.models.schemas import MissingSuggestion

_IMAGE_EXPECTATIONS = [
    ("Author / Creator", ["Artist", "Creator"], "Common for photos exported from editing software or shot with a camera configured with an owner name."),
    ("Capture Date", ["DateTimeOriginal", "CreateDate"], "Usually present on camera/phone photos; often absent on screenshots or AI-generated/edited images."),
    ("Camera Make/Model", ["Make", "Model"], "Present when a physical camera or phone captured the image; absent for scans, screenshots, or synthetic images."),
    ("Copyright", ["Copyright", "Rights"], "Common in professionally distributed or stock photography."),
    ("Description / Caption", ["Description", "Caption-Abstract", "ImageDescription"], "Common in catalogued or press/stock imagery."),
]

_MEDIA_EXPECTATIONS = [
    ("Title", ["title"], "Common when exported from editing software with project metadata."),
    ("Creation Date", ["creation_time"], "Usually set automatically by recording devices and most editing software."),
    ("Encoder/Software", ["encoder"], "Set by the tool that produced or last re-encoded the file."),
]

_OFFICE_EXPECTATIONS = [
    ("Author", ["author"], "Set by the authoring application from the OS/account username unless cleared."),
    ("Title", ["title"], "Often left blank unless explicitly filled in via File > Properties."),
    ("Last Modified By", ["last_modified_by"], "Updated automatically by the authoring application on each save."),
]

_PDF_EXPECTATIONS = [
    ("Title", ["title"], "Commonly set by the export tool (word processor, LaTeX, scanner software)."),
    ("Author", ["author"], "Often populated automatically from the authoring application's account name."),
    ("Producer", ["producer"], "Almost always set automatically by the PDF-generating library/application."),
]


def _domain_for(section_ids: set[str]) -> str | None:
    if {"exif", "gps", "camera", "author", "image_technical"} & section_ids:
        return "image"
    if {"media_container", "media_video_streams", "media_audio_streams", "media_tags"} & section_ids:
        return "media"
    if {"office_core", "office_structure"} & section_ids:
        return "office"
    if {"pdf_document", "pdf_structure"} & section_ids:
        return "pdf"
    return None


def _bare_tag_name(key: str) -> str:
    return key.split(":", 1)[-1] if ":" in key else key


def suggest_missing_fields(sections) -> list[MissingSuggestion]:
    section_ids = {s.section_id for s in sections}
    domain = _domain_for(section_ids)
    if domain is None:
        return []

    present_tag_names = {
        _bare_tag_name(f.key) for s in sections for f in s.fields
        if f.normalized_value not in (None, "") and f.namespace != "Composite"
    }

    expectations = {
        "image": _IMAGE_EXPECTATIONS,
        "media": _MEDIA_EXPECTATIONS,
        "office": _OFFICE_EXPECTATIONS,
        "pdf": _PDF_EXPECTATIONS,
    }[domain]

    out: list[MissingSuggestion] = []
    for logical_name, candidate_names, note in expectations:
        if not any(name in present_tag_names for name in candidate_names):
            out.append(MissingSuggestion(logical_name=logical_name, candidate_keys=candidate_names, note=note))
    return out
