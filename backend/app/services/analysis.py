"""Orchestrates identification, hashing, and all applicable parsers into a
single AnalysisResult."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from app.models.schemas import AnalysisResult, Capability, FileIdentity
from app.parsers.base import all_parsers, parsers_for
from app.services import duplicates, hashing, identify, size_analysis, stream_integrity, suggestions
from app.services.timestamps import detect_and_annotate


def _fs_time(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def analyze_file(file_id: str, path: Path, original_filename: str, sanitized_filename: str) -> AnalysisResult:
    st = path.stat()
    id_info = identify.identify_file(path)

    identity = FileIdentity(
        original_filename=original_filename,
        sanitized_filename=sanitized_filename,
        detected_format=id_info["detected_format"],
        mime_type=id_info["mime_type"],
        extension=id_info["extension"],
        size_bytes=st.st_size,
        size_human=identify.human_size(st.st_size),
        magic_bytes_hex=id_info["magic_bytes_hex"],
        extension_matches_format=id_info["extension_matches_format"],
        expected_extensions=id_info.get("expected_extensions", []),
        fs_created=_fs_time(getattr(st, "st_birthtime", st.st_ctime)),
        fs_modified=_fs_time(st.st_mtime),
        fs_accessed=_fs_time(st.st_atime),
    )

    file_hashes = hashing.compute_hashes(path)
    entropy, histogram = hashing.compute_entropy_and_histogram(path)

    applicable = parsers_for(identity.detected_format, identity.mime_type, identity.extension)
    capabilities: list[Capability] = []
    sections = []
    warnings: list[str] = []

    if not identity.extension_matches_format:
        warnings.append(
            f"File extension '.{identity.extension}' does not match the detected format "
            f"'{identity.detected_format}'. The content was analyzed by its real format, not its name."
        )

    seen_section_ids = set()
    for parser in applicable:
        try:
            capabilities.extend(parser.get_capabilities(path))
        except Exception as exc:
            warnings.append(f"{parser.name} capability check failed: {exc}")
        try:
            parser_sections = parser.extract_metadata(path)
        except Exception as exc:
            warnings.append(f"{parser.name} parser raised an unexpected error: {exc}")
            continue
        for s in parser_sections:
            if s.section_id in seen_section_ids:
                s.section_id = f"{s.section_id}_{parser.name}"
            seen_section_ids.add(s.section_id)
            sections.append(s)

    if not applicable:
        warnings.append("No specialized parser recognized this format; only identity, hashing, and binary analysis were performed.")

    # --- Timestamp Normalizer: centralized pass over every field from every
    # parser, so EXIF/IPTC/XMP (exiftool-style) and ffprobe/PDF/Office
    # (ISO-8601-ish) timestamps are all annotated consistently. ---
    for section in sections:
        for field in section.fields:
            is_ts, forced_type, ts_utc, ts_has_tz = detect_and_annotate(field.normalized_value)
            if is_ts:
                field.is_timestamp = True
                if forced_type:
                    field.value_type = forced_type
                field.timestamp_utc = ts_utc
                field.timestamp_has_tz = ts_has_tz

    # --- Duplicate Metadata Detector ---
    duplicate_groups = duplicates.detect_duplicates(sections)

    # --- Missing Metadata Suggestions ---
    missing_suggestions = suggestions.suggest_missing_fields(sections)

    # --- Metadata Size Analyzer ---
    metadata_size = size_analysis.analyze_metadata_size(path, identity.detected_format, identity.extension)

    # --- Appended-data-after-EOF forensic flag (bonus feature) ---
    appended_data = stream_integrity.detect_appended_data(path, identity.detected_format)

    return AnalysisResult(
        file_id=file_id,
        identity=identity,
        hashes=file_hashes,
        capabilities=capabilities,
        sections=sections,
        entropy=entropy,
        histogram=histogram,
        parser_warnings=warnings,
        metadata_size=metadata_size,
        duplicate_groups=duplicate_groups,
        missing_suggestions=missing_suggestions,
        appended_data=appended_data,
    )
