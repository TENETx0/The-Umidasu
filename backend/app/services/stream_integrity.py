"""Save Without Recompression — verifies, by direct byte comparison of the
actual compressed pixel/sample data, whether a metadata-only edit left the
real image/video stream byte-for-byte identical.

ExifTool (used for all EXIF/IPTC/XMP/GPS/QuickTime-tag edits in this app)
is designed to rewrite only metadata segments/atoms and never decodes or
re-encodes pixel/audio/video streams. This module does not just assume
that claim — it verifies it structurally, before and after, so the report
shown to the user is a measured fact, not a hopeful assertion. For formats
we have no verifier for, we say so honestly rather than claim success.

Also provides the appended-data-after-EOF detector: a classic forensic
check for bytes hidden after a JPEG EOI or PNG IEND marker.
"""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path


def jpeg_scan_hash(path: Path) -> str | None:
    """Hash of everything from the Start-Of-Scan marker to EOF (or EOI),
    i.e. the actual entropy-coded compressed image data, not the headers
    or metadata segments that precede it."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
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
            if marker == 0xDA:  # SOS — scan data starts right after this segment's header
                seg_len = struct.unpack(">H", data[pos + 2:pos + 4])[0]
                scan_start = pos + 2 + seg_len
                return hashlib.sha256(data[scan_start:]).hexdigest()
            if pos + 4 > len(data):
                break
            seg_len = struct.unpack(">H", data[pos + 2:pos + 4])[0]
            pos += 2 + seg_len
    except (struct.error, IndexError):
        return None
    return None


def png_idat_hash(path: Path) -> str | None:
    """Hash of all concatenated IDAT chunk payloads (the actual compressed
    pixel data), independent of ancillary metadata chunks."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 8 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos = 8
    idat_bytes = bytearray()
    try:
        while pos + 8 <= len(data):
            length = struct.unpack(">I", data[pos:pos + 4])[0]
            ctype = data[pos + 4:pos + 8]
            chunk_data_start = pos + 8
            if ctype == b"IDAT":
                idat_bytes.extend(data[chunk_data_start:chunk_data_start + length])
            pos = chunk_data_start + length + 4
            if ctype == b"IEND":
                break
    except (struct.error, IndexError):
        return None
    if not idat_bytes:
        return None
    return hashlib.sha256(bytes(idat_bytes)).hexdigest()


def mp4_mdat_hash(path: Path) -> str | None:
    """Hash of all top-level 'mdat' box payloads (the actual audio/video
    sample data), independent of 'moov'/metadata boxes."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 8:
        return None
    pos = 0
    mdat_bytes = bytearray()
    found_any = False
    try:
        while pos + 8 <= len(data):
            size = struct.unpack(">I", data[pos:pos + 4])[0]
            box_type = data[pos + 4:pos + 8]
            header_len = 8
            if size == 1:  # 64-bit extended size
                if pos + 16 > len(data):
                    break
                size = struct.unpack(">Q", data[pos + 8:pos + 16])[0]
                header_len = 16
            if size == 0:  # box extends to EOF
                size = len(data) - pos
            if box_type == b"mdat":
                mdat_bytes.extend(data[pos + header_len:pos + size])
                found_any = True
            if size < header_len:
                break
            pos += size
    except (struct.error, IndexError):
        return None
    if not found_any:
        return None
    return hashlib.sha256(bytes(mdat_bytes)).hexdigest()


_VERIFIERS = {
    "jpg": ("jpeg_scan_data", jpeg_scan_hash),
    "jpeg": ("jpeg_scan_data", jpeg_scan_hash),
    "png": ("png_idat_chunks", png_idat_hash),
    "mp4": ("mp4_mdat_box", mp4_mdat_hash),
    "mov": ("mp4_mdat_box", mp4_mdat_hash),
    "m4v": ("mp4_mdat_box", mp4_mdat_hash),
    "m4a": ("mp4_mdat_box", mp4_mdat_hash),
}


def stream_preservation_report(before_path: Path, after_path: Path, extension: str) -> dict:
    """Compare the real media stream of `before_path` and `after_path`.
    Returns a dict describing whether the edit preserved the stream
    byte-for-byte, with an honest `measured=False` for formats we have no
    structural verifier for (rather than a false claim of success)."""
    entry = _VERIFIERS.get(extension.lower())
    if entry is None:
        return {
            "measured": False,
            "method": "not_supported",
            "preserved": None,
            "note": (
                "No structural stream verifier is implemented for this format. The editing tool used "
                "(exiftool for tag edits) is documented to rewrite only metadata, not pixel/audio/video "
                "streams, but this specific claim was not independently verified for this file."
            ),
        }
    method, fn = entry
    before_hash = fn(before_path)
    after_hash = fn(after_path)
    if before_hash is None or after_hash is None:
        return {
            "measured": False,
            "method": method,
            "preserved": None,
            "note": "Could not locate the expected stream structure to compare (file may be malformed or unusually structured).",
        }
    preserved = before_hash == after_hash
    return {
        "measured": True,
        "method": method,
        "preserved": preserved,
        "before_hash": before_hash,
        "after_hash": after_hash,
        "note": (
            "Compressed image/media stream is byte-for-byte identical — no recompression occurred."
            if preserved else
            "WARNING: the compressed stream changed. This edit was NOT metadata-only — investigate before relying on this output."
        ),
    }


def detect_appended_data(path: Path, detected_format: str) -> dict | None:
    """Classic forensic check: bytes present after the format's own
    logical end-of-file marker (JPEG EOI / PNG IEND) often indicate
    deliberately appended hidden data (a common steganography/exfiltration
    technique). Returns None when not applicable to this format."""
    try:
        data = path.read_bytes()
    except OSError:
        return None

    if detected_format == "JPEG" and data[:2] == b"\xff\xd8":
        eoi = data.rfind(b"\xff\xd9")
        if eoi == -1:
            return {"checked": True, "trailing_bytes": None, "note": "No EOI marker found; file may be truncated."}
        trailing = len(data) - (eoi + 2)
        return {
            "checked": True,
            "trailing_bytes": trailing,
            "note": (
                f"{trailing} byte(s) found after the JPEG end-of-image (EOI) marker. This region is ignored "
                "by image viewers and can be used to hide arbitrary data."
                if trailing > 0 else
                "No data found after the end-of-image marker."
            ),
        }

    if detected_format == "PNG" and data[:8] == b"\x89PNG\r\n\x1a\n":
        iend = data.rfind(b"IEND")
        if iend == -1:
            return {"checked": True, "trailing_bytes": None, "note": "No IEND chunk found; file may be truncated."}
        end_of_iend = iend + 4 + 4  # "IEND" + 4-byte CRC
        trailing = len(data) - end_of_iend
        return {
            "checked": True,
            "trailing_bytes": trailing,
            "note": (
                f"{trailing} byte(s) found after the PNG IEND chunk. This region is ignored by image viewers "
                "and can be used to hide arbitrary data."
                if trailing > 0 else
                "No data found after the IEND chunk."
            ),
        }

    return None
