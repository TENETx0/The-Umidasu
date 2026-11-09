"""Format identification independent of filename/extension.

Combines libmagic (when available), a small set of well-known magic-byte
signatures as a fallback, and extension comparison so the result reports
whether the claimed extension actually agrees with the detected content.
"""
from __future__ import annotations

from pathlib import Path

try:
    import magic as _magic  # python-magic (libmagic binding)
    _HAVE_MAGIC = True
except Exception:  # pragma: no cover - environment dependent
    _magic = None
    _HAVE_MAGIC = False

# (signature bytes, offset, format name, typical extensions)
_SIGNATURES: list[tuple[bytes, int, str, list[str]]] = [
    (b"\xff\xd8\xff", 0, "JPEG", ["jpg", "jpeg"]),
    (b"\x89PNG\r\n\x1a\n", 0, "PNG", ["png"]),
    (b"GIF87a", 0, "GIF", ["gif"]),
    (b"GIF89a", 0, "GIF", ["gif"]),
    (b"BM", 0, "BMP", ["bmp"]),
    (b"RIFF", 0, "RIFF (WEBP/WAV/AVI)", ["webp", "wav", "avi"]),
    (b"II*\x00", 0, "TIFF (little-endian)", ["tif", "tiff"]),
    (b"MM\x00*", 0, "TIFF (big-endian)", ["tif", "tiff"]),
    (b"%PDF-", 0, "PDF", ["pdf"]),
    (b"PK\x03\x04", 0, "ZIP/OOXML", ["zip", "docx", "xlsx", "pptx", "jar", "apk"]),
    (b"PK\x05\x06", 0, "ZIP (empty archive)", ["zip"]),
    (b"\x1f\x8b", 0, "GZIP", ["gz", "tgz"]),
    (b"ustar", 257, "TAR", ["tar"]),
    (b"7z\xbc\xaf\x27\x1c", 0, "7-Zip", ["7z"]),
    (b"Rar!\x1a\x07", 0, "RAR", ["rar"]),
    (b"\x00\x00\x00\x18ftyp", 4, "MP4/MOV (ISO-BMFF)", ["mp4", "mov", "m4a", "m4v"]),
    (b"\x00\x00\x00\x1cftyp", 4, "MP4/MOV (ISO-BMFF)", ["mp4", "mov", "m4a", "m4v"]),
    (b"ftyp", 4, "MP4/MOV (ISO-BMFF)", ["mp4", "mov", "m4a", "m4v"]),
    (b"\x1a\x45\xdf\xa3", 0, "Matroska/WebM", ["mkv", "webm"]),
    (b"ID3", 0, "MP3 (ID3 tag)", ["mp3"]),
    (b"\xff\xfb", 0, "MP3 (MPEG audio)", ["mp3"]),
    (b"fLaC", 0, "FLAC", ["flac"]),
    (b"OggS", 0, "OGG", ["ogg", "oga"]),
    (b"\x7fELF", 0, "ELF executable", ["elf", "so", "bin"]),
    (b"MZ", 0, "PE/DOS executable", ["exe", "dll"]),
    (b"\xca\xfe\xba\xbe", 0, "Mach-O (fat) / Java class", ["class"]),
    (b"\xfe\xed\xfa\xce", 0, "Mach-O (32-bit)", ["o", "dylib"]),
    (b"\xfe\xed\xfa\xcf", 0, "Mach-O (64-bit)", ["o", "dylib"]),
    (b"<?xml", 0, "XML", ["xml", "svg"]),
    (b"<svg", 0, "SVG", ["svg"]),
]

_MIME_BY_FORMAT = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "GIF": "image/gif",
    "BMP": "image/bmp",
    "TIFF (little-endian)": "image/tiff",
    "TIFF (big-endian)": "image/tiff",
    "PDF": "application/pdf",
    "ZIP/OOXML": "application/zip",
    "GZIP": "application/gzip",
    "TAR": "application/x-tar",
    "7-Zip": "application/x-7z-compressed",
    "RAR": "application/vnd.rar",
    "MP4/MOV (ISO-BMFF)": "video/mp4",
    "Matroska/WebM": "video/webm",
    "MP3 (ID3 tag)": "audio/mpeg",
    "MP3 (MPEG audio)": "audio/mpeg",
    "FLAC": "audio/flac",
    "OGG": "audio/ogg",
    "ELF executable": "application/x-elf",
    "PE/DOS executable": "application/x-dosexec",
    "XML": "application/xml",
    "SVG": "image/svg+xml",
}


def read_head(path: Path, n: int = 512) -> bytes:
    with path.open("rb") as f:
        return f.read(n)


def detect_by_signature(head: bytes) -> tuple[str, list[str]] | None:
    for sig, offset, fmt, exts in _SIGNATURES:
        end = offset + len(sig)
        if len(head) >= end and head[offset:end] == sig:
            return fmt, exts
    return None


def detect_mime(path: Path) -> str:
    if _HAVE_MAGIC:
        try:
            return _magic.from_file(str(path), mime=True)
        except Exception:
            pass
    return "application/octet-stream"


def identify_file(path: Path) -> dict:
    head = read_head(path, 4096)
    sig_match = detect_by_signature(head)
    detected_format = sig_match[0] if sig_match else "Unknown/Binary"
    expected_exts = sig_match[1] if sig_match else []

    mime = detect_mime(path)
    if mime == "application/octet-stream" and detected_format in _MIME_BY_FORMAT:
        mime = _MIME_BY_FORMAT[detected_format]

    ext = path.suffix.lower().lstrip(".")
    extension_matches = (not expected_exts) or (ext in expected_exts)
    # If we truly have no signature match, we can't claim a mismatch.
    if detected_format == "Unknown/Binary":
        extension_matches = True

    return {
        "detected_format": detected_format,
        "mime_type": mime,
        "extension": ext,
        "magic_bytes_hex": head[:16].hex(" "),
        "extension_matches_format": extension_matches,
        "expected_extensions": expected_exts,
    }


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0 or unit == "TB":
            return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0
    return f"{num_bytes} B"
