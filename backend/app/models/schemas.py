"""Pydantic data models shared across the backend."""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ExtractionStatus(str, Enum):
    SUCCESS = "extracted_successfully"
    NO_METADATA = "no_relevant_metadata_found"
    NOT_SUPPORTED = "not_supported_for_this_format"
    FAILED = "extraction_failed"
    NOT_ANALYZED = "not_analyzed"


class FileHashes(BaseModel):
    md5: str
    sha1: str
    sha256: str
    sha512: str
    security_notes: dict[str, str] = Field(default_factory=dict)


class MetadataField(BaseModel):
    """One extracted (and potentially editable) metadata field."""

    key: str  # stable machine key, e.g. "EXIF:GPSLatitude"
    group: str  # e.g. "EXIF", "IPTC", "XMP", "Container", "Core Properties"
    label: str  # human readable label
    raw_value: Any = None
    normalized_value: Any = None
    value_type: str = "string"  # string|number|boolean|date|coordinate|array|object
    source_parser: str = ""
    writable: bool = False
    sensitive: bool = False
    confidence: Optional[str] = None
    notes: Optional[str] = None

    # --- Unknown Tag Decoder ---
    tag_id: Optional[str] = None  # exiftool tag ID, e.g. "0x010f" (hex) when known
    namespace: Optional[str] = None  # exiftool group/namespace, e.g. "EXIF", "XMP-dc"
    is_unknown_tag: bool = False  # True if this tag name is not in our curated "common tags" list

    # --- GPS Coordinate Converter ---
    representations: Optional[dict[str, str]] = None  # {"decimal": .., "dms": .., "ddm": ..}

    # --- Timestamp Normalizer ---
    is_timestamp: bool = False
    timestamp_utc: Optional[str] = None  # ISO-8601 UTC, only when the source string carried an explicit offset
    timestamp_has_tz: bool = False  # whether the raw value carried explicit timezone/offset info

    # --- Duplicate / change-history correlation ---
    diff_status: Optional[str] = None  # "added" | "removed" | "modified" | None (unchanged) — filled in by the diff service, not the parser


class MetadataSection(BaseModel):
    section_id: str
    title: str
    status: ExtractionStatus
    fields: list[MetadataField] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    detail_message: Optional[str] = None


class Capability(BaseModel):
    name: str
    available: bool
    reason: Optional[str] = None


class FileIdentity(BaseModel):
    original_filename: str
    sanitized_filename: str
    detected_format: str
    mime_type: str
    extension: str
    size_bytes: int
    size_human: str
    magic_bytes_hex: str
    extension_matches_format: bool
    expected_extensions: list[str] = Field(default_factory=list)  # File Extension Mismatch Warning
    fs_created: Optional[str] = None
    fs_modified: Optional[str] = None
    fs_accessed: Optional[str] = None


class MetadataSizeInfo(BaseModel):
    """Metadata Size Analyzer result — how many bytes of the file are
    metadata vs. actual content, only for formats where this is reliably
    measurable by direct structural parsing (never estimated/guessed)."""

    measured: bool
    method: str  # e.g. "jpeg_app_segments", "png_text_chunks", "office_docprops", "pdf_info_and_xmp", "not_supported"
    metadata_bytes: int = 0
    total_bytes: int = 0
    percentage: float = 0.0
    note: Optional[str] = None


class DuplicateGroup(BaseModel):
    """Duplicate Metadata Detector result — fields that express the same
    real-world concept (author, date, description, ...) across different
    tag namespaces, flagged as redundant (identical values) or conflicting
    (differing values)."""

    concept: str
    status: str  # "redundant" | "conflicting"
    fields: list[dict[str, Any]]  # [{"key":.., "label":.., "value":..}, ...]


class MissingSuggestion(BaseModel):
    """Missing Metadata Suggestions — commonly-present fields absent from
    this file, phrased neutrally (not as a defect)."""

    logical_name: str
    candidate_keys: list[str]
    note: str


class AnalysisResult(BaseModel):
    file_id: str
    identity: FileIdentity
    hashes: FileHashes
    capabilities: list[Capability]
    sections: list[MetadataSection]
    entropy: float
    histogram: list[int]
    parser_warnings: list[str] = Field(default_factory=list)
    metadata_size: Optional[MetadataSizeInfo] = None
    duplicate_groups: list[DuplicateGroup] = Field(default_factory=list)
    missing_suggestions: list[MissingSuggestion] = Field(default_factory=list)
    appended_data: Optional[dict[str, Any]] = None  # trailing-data-after-EOF forensic flag


class EditOperation(BaseModel):
    op_id: str
    field_key: str
    group: str
    action: str  # "set" | "remove"
    old_value: Any = None
    new_value: Any = None
    timestamp: str


class PendingEditsRequest(BaseModel):
    edits: list[dict] = Field(default_factory=list)


class CustomTimestamps(BaseModel):
    created: Optional[str] = None  # ISO 8601
    modified: Optional[str] = None
    accessed: Optional[str] = None


class RemovalPresetRequest(BaseModel):
    presets: list[str]


class SaveAsResult(BaseModel):
    output_file_id: str
    output_filename: str
    output_hashes: FileHashes
    verification: dict[str, Any]
    unsupported_edits: list[dict] = Field(default_factory=list)
    failed_edits: list[dict] = Field(default_factory=list)


# ------------------------------------------------------------- snapshots --
class MetadataSnapshot(BaseModel):
    """One-Click Metadata Snapshot — a captured map of writable field
    values at a point in time, restorable later."""

    snapshot_id: str
    label: str
    created_at: str
    field_map: dict[str, Any] = Field(default_factory=dict)  # key -> normalized_value, writable fields only


class SnapshotRequest(BaseModel):
    label: Optional[str] = None


class DiffEntry(BaseModel):
    key: str
    label: Optional[str] = None
    before: Any = None
    after: Any = None


class MetadataDiff(BaseModel):
    added: list[DiffEntry] = Field(default_factory=list)
    removed: list[DiffEntry] = Field(default_factory=list)
    modified: list[DiffEntry] = Field(default_factory=list)
    baseline_label: str = "Original"


# ------------------------------------------------------- copy & paste -----
class CopyMetadataRequest(BaseModel):
    source_file_id: str
    field_keys: Optional[list[str]] = None  # None/empty = all compatible fields with a value


class CopyFieldResult(BaseModel):
    key: str
    label: str
    value: Any
    compatible: bool
    staged: bool
    reason: Optional[str] = None


class CopyMetadataResponse(BaseModel):
    results: list[CopyFieldResult]
    staged_count: int


# ------------------------------------------------------------- presets ---
class PresetLogicalFields(BaseModel):
    author: Optional[str] = None
    copyright: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None


class MetadataPreset(BaseModel):
    preset_id: str
    name: str
    fields: PresetLogicalFields
    created_at: str


class CreatePresetRequest(BaseModel):
    name: str
    fields: PresetLogicalFields


class ApplyPresetResponse(BaseModel):
    staged: list[dict]
    skipped: list[dict]
