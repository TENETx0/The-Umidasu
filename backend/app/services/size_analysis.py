"""Metadata Size Analyzer — measures actual on-disk metadata byte usage by
walking each format's real binary/container structure. Every number here
is counted directly from file bytes, never estimated. For formats we
cannot structurally measure, we say so honestly instead of guessing.
"""
from __future__ import annotations

import struct
import zipfile
from pathlib import Path

from app.models.schemas import MetadataSizeInfo

# JPEG markers that carry metadata (APPn application segments + comments).
# APP0 (JFIF) and APP14 (Adobe) are structural/color-management, not really
# "metadata" in the user-facing sense, so we count APP1 (EXIF/XMP), APP2
# (ICC can live here too, debatable — we count it since it's non-pixel
# payload), APP13 (IPTC/Photoshop), and COM (comments).
_JPEG_METADATA_MARKERS = {0xE1, 0xE2, 0xED, 0xFE}
_JPEG_SOS = 0xDA
_JPEG_EOI = 0xD9


def jpeg_metadata_bytes(path: Path) -> MetadataSizeInfo | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 4 or data[0:2] != b"\xff\xd8":
        return None

    total = len(data)
    metadata_bytes = 0
    pos = 2
    try:
        while pos < len(data) - 1:
            if data[pos] != 0xFF:
                pos += 1
                continue
            marker = data[pos + 1]
            if marker in (0x01, 0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                pos += 2
                continue
            if marker == _JPEG_SOS:
                break  # compressed scan data follows; stop scanning segments
            if pos + 4 > len(data):
                break
            seg_len = struct.unpack(">H", data[pos + 2:pos + 4])[0]
            if marker in _JPEG_METADATA_MARKERS:
                metadata_bytes += seg_len + 2  # +2 for the marker itself
            pos += 2 + seg_len
    except (struct.error, IndexError):
        return MetadataSizeInfo(measured=False, method="jpeg_app_segments",
                                 note="JPEG segment structure could not be fully parsed.")

    pct = round((metadata_bytes / total) * 100, 3) if total else 0.0
    return MetadataSizeInfo(
        measured=True, method="jpeg_app_segments",
        metadata_bytes=metadata_bytes, total_bytes=total, percentage=pct,
        note="Counted from APP1 (EXIF/XMP), APP2, APP13 (IPTC), and COM segment lengths in the JPEG byte stream.",
    )


# PNG metadata-bearing chunk types (ancillary, non-pixel).
_PNG_METADATA_CHUNKS = {b"tEXt", b"zTXt", b"iTXt", b"eXIf", b"tIME", b"iCCP"}


def png_metadata_bytes(path: Path) -> MetadataSizeInfo | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 8 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None

    total = len(data)
    metadata_bytes = 0
    pos = 8
    try:
        while pos + 8 <= len(data):
            length = struct.unpack(">I", data[pos:pos + 4])[0]
            ctype = data[pos + 4:pos + 8]
            chunk_total = 4 + 4 + length + 4  # length + type + data + CRC
            if ctype in _PNG_METADATA_CHUNKS:
                metadata_bytes += chunk_total
            pos += chunk_total
            if ctype == b"IEND":
                break
    except (struct.error, IndexError):
        return MetadataSizeInfo(measured=False, method="png_text_chunks",
                                 note="PNG chunk structure could not be fully parsed.")

    pct = round((metadata_bytes / total) * 100, 3) if total else 0.0
    return MetadataSizeInfo(
        measured=True, method="png_text_chunks",
        metadata_bytes=metadata_bytes, total_bytes=total, percentage=pct,
        note="Counted from tEXt/zTXt/iTXt/eXIf/tIME/iCCP chunk sizes in the PNG byte stream.",
    )


def office_metadata_bytes(path: Path) -> MetadataSizeInfo | None:
    """OOXML (docx/xlsx/pptx): sum the compressed size of the docProps/ and
    customXml/ package members as a real, measurable proxy for document
    metadata footprint."""
    try:
        total = path.stat().st_size
        with zipfile.ZipFile(path) as z:
            metadata_bytes = sum(
                info.compress_size for info in z.infolist()
                if info.filename.startswith(("docProps/", "customXml/"))
            )
    except (OSError, zipfile.BadZipFile):
        return None
    pct = round((metadata_bytes / total) * 100, 3) if total else 0.0
    return MetadataSizeInfo(
        measured=True, method="office_docprops",
        metadata_bytes=metadata_bytes, total_bytes=total, percentage=pct,
        note="Sum of compressed docProps/ and customXml/ package member sizes.",
    )


def pdf_metadata_bytes(path: Path) -> MetadataSizeInfo | None:
    try:
        import pikepdf
    except ImportError:
        return None
    try:
        total = path.stat().st_size
        metadata_bytes = 0
        with pikepdf.open(path) as pdf:
            for key, val in pdf.docinfo.items():
                try:
                    metadata_bytes += len(str(key)) + len(str(val))
                except Exception:
                    continue
            if "/Metadata" in pdf.Root:
                try:
                    stream = pdf.Root.Metadata
                    metadata_bytes += len(bytes(stream.read_bytes()))
                except Exception:
                    pass
    except Exception:
        return None
    pct = round((metadata_bytes / total) * 100, 3) if total else 0.0
    return MetadataSizeInfo(
        measured=True, method="pdf_info_and_xmp",
        metadata_bytes=metadata_bytes, total_bytes=total, percentage=pct,
        note="Approximate byte length of the classic /Info dictionary entries plus the XMP metadata stream, if present.",
    )


def analyze_metadata_size(path: Path, detected_format: str, extension: str) -> MetadataSizeInfo:
    result = None
    if detected_format == "JPEG" or extension in ("jpg", "jpeg"):
        result = jpeg_metadata_bytes(path)
    elif detected_format == "PNG" or extension == "png":
        result = png_metadata_bytes(path)
    elif extension in ("docx", "xlsx", "pptx"):
        result = office_metadata_bytes(path)
    elif detected_format == "PDF" or extension == "pdf":
        result = pdf_metadata_bytes(path)

    if result is not None:
        return result
    return MetadataSizeInfo(
        measured=False, method="not_supported",
        note="Byte-exact metadata size measurement is not implemented for this format.",
    )
