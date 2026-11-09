"""Generic binary/encoding analysis: always runs, regardless of format.

Encoding detection, printable strings, hex preview, ELF/PE header peek.
Never decodes, decompresses, or executes anything automatically.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.core.config import settings
from app.models.schemas import Capability, ExtractionStatus, MetadataField, MetadataSection
from app.parsers.base import BaseParser, register

_PRINTABLE_RE = re.compile(rb"[\x20-\x7e]{%d,}" % settings.STRINGS_MIN_LENGTH)


def _detect_bom(head: bytes) -> str | None:
    boms = [
        (b"\xef\xbb\xbf", "UTF-8"),
        (b"\xff\xfe\x00\x00", "UTF-32 LE"),
        (b"\x00\x00\xfe\xff", "UTF-32 BE"),
        (b"\xff\xfe", "UTF-16 LE"),
        (b"\xfe\xff", "UTF-16 BE"),
    ]
    for sig, name in boms:
        if head.startswith(sig):
            return name
    return None


def _is_valid_utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _extract_strings(path: Path, max_bytes: int, min_len: int, max_results: int) -> list[str]:
    results: list[str] = []
    with path.open("rb") as f:
        data = f.read(max_bytes)
    for m in re.finditer(rb"[\x20-\x7e]{%d,}" % min_len, data):
        results.append(m.group().decode("ascii"))
        if len(results) >= max_results:
            break
    return results


class BinaryParser(BaseParser):
    name = "binary"

    def supports(self, detected_format: str, mime_type: str, extension: str) -> bool:
        return True  # runs for every file, supplementing format-specific parsers

    def get_capabilities(self, path: Path) -> list[Capability]:
        return [
            Capability(name="Encoding/BOM detection", available=True),
            Capability(name="Printable string extraction", available=True),
            Capability(name="Hex/ASCII preview", available=True),
        ]

    def extract_metadata(self, path: Path) -> list[MetadataSection]:
        section = MetadataSection(section_id="binary_analysis", title="Encoding & Binary Analysis", status=ExtractionStatus.NOT_ANALYZED)
        try:
            with path.open("rb") as f:
                head = f.read(65536)

            bom = _detect_bom(head)
            is_utf8 = _is_valid_utf8(head)
            null_byte_present = b"\x00" in head
            appears_binary = null_byte_present or not is_utf8

            fields = [
                MetadataField(key="bin:bom", group="Encoding", label="Byte Order Mark",
                              raw_value=bom, normalized_value=bom or "None detected", value_type="string", source_parser="heuristic"),
                MetadataField(key="bin:valid_utf8_sample", group="Encoding", label="First 64KB Valid UTF-8",
                              raw_value=is_utf8, normalized_value=is_utf8, value_type="boolean", source_parser="heuristic"),
                MetadataField(key="bin:contains_null_bytes", group="Encoding", label="Contains NUL Bytes (first 64KB)",
                              raw_value=null_byte_present, normalized_value=null_byte_present, value_type="boolean", source_parser="heuristic"),
                MetadataField(key="bin:appears_binary", group="Encoding", label="Appears Binary (heuristic)",
                              raw_value=appears_binary, normalized_value=appears_binary, value_type="boolean", source_parser="heuristic",
                              notes="Heuristic only: NUL bytes present or sample is not valid UTF-8."),
            ]

            hex_preview = head[:settings.HEX_PREVIEW_BYTES]
            fields.append(MetadataField(
                key="bin:hex_preview", group="Hex View", label=f"First {len(hex_preview)} Bytes (hex)",
                raw_value=hex_preview.hex(), normalized_value=hex_preview.hex(), value_type="string", source_parser="hexdump"))

            strings = _extract_strings(path, max_bytes=min(path.stat().st_size, 4 * 1024 * 1024),
                                        min_len=settings.STRINGS_MIN_LENGTH, max_results=settings.STRINGS_MAX_RESULTS)
            fields.append(MetadataField(
                key="bin:printable_strings", group="Strings", label=f"Printable Strings (min length {settings.STRINGS_MIN_LENGTH}, max {settings.STRINGS_MAX_RESULTS})",
                raw_value=strings, normalized_value=f"{len(strings)} strings found", value_type="array", source_parser="regex"))

            # ELF/PE header peek
            if head[:4] == b"\x7fELF":
                ei_class = {1: "32-bit", 2: "64-bit"}.get(head[4], "unknown")
                ei_data = {1: "little-endian", 2: "big-endian"}.get(head[5], "unknown")
                fields.append(MetadataField(key="bin:elf_class", group="ELF Header", label="ELF Class", raw_value=ei_class, normalized_value=ei_class, value_type="string", source_parser="header-parse"))
                fields.append(MetadataField(key="bin:elf_endian", group="ELF Header", label="Endianness", raw_value=ei_data, normalized_value=ei_data, value_type="string", source_parser="header-parse"))
            elif head[:2] == b"MZ":
                fields.append(MetadataField(key="bin:pe_marker", group="PE Header", label="DOS/PE Marker", raw_value="MZ", normalized_value="MZ (DOS stub present)", value_type="string", source_parser="header-parse"))

            section.fields = fields
            section.status = ExtractionStatus.SUCCESS
        except Exception as exc:
            section.status = ExtractionStatus.FAILED
            section.detail_message = str(exc)

        return [section]


register(BinaryParser())
