export type ExtractionStatus =
  | "extracted_successfully"
  | "no_relevant_metadata_found"
  | "not_supported_for_this_format"
  | "extraction_failed"
  | "not_analyzed";

export interface FileHashes {
  md5: string;
  sha1: string;
  sha256: string;
  sha512: string;
  security_notes: Record<string, string>;
}

export interface MetadataField {
  key: string;
  group: string;
  label: string;
  raw_value: unknown;
  normalized_value: unknown;
  value_type: string;
  source_parser: string;
  writable: boolean;
  sensitive: boolean;
  confidence?: string | null;
  notes?: string | null;

  // --- Unknown Tag Decoder ---
  tag_id?: string | null;
  namespace?: string | null;
  is_unknown_tag: boolean;

  // --- GPS Coordinate Converter ---
  representations?: Record<string, string> | null;

  // --- Timestamp Normalizer ---
  is_timestamp: boolean;
  timestamp_utc?: string | null;
  timestamp_has_tz: boolean;

  // --- Metadata Difference Highlighting (filled in client-side) ---
  diff_status?: "added" | "removed" | "modified" | null;
}

export interface MetadataSection {
  section_id: string;
  title: string;
  status: ExtractionStatus;
  fields: MetadataField[];
  warnings: string[];
  detail_message?: string | null;
}

export interface Capability {
  name: string;
  available: boolean;
  reason?: string | null;
}

export interface FileIdentity {
  original_filename: string;
  sanitized_filename: string;
  detected_format: string;
  mime_type: string;
  extension: string;
  size_bytes: number;
  size_human: string;
  magic_bytes_hex: string;
  extension_matches_format: boolean;
  expected_extensions: string[];
  fs_created?: string | null;
  fs_modified?: string | null;
  fs_accessed?: string | null;
}

export interface MetadataSizeInfo {
  measured: boolean;
  method: string;
  metadata_bytes: number;
  total_bytes: number;
  percentage: number;
  note?: string | null;
}

export interface DuplicateGroup {
  concept: string;
  status: "redundant" | "conflicting";
  fields: { key: string; label: string; value: unknown }[];
}

export interface MissingSuggestion {
  logical_name: string;
  candidate_keys: string[];
  note: string;
}

export interface AnalysisResult {
  file_id: string;
  identity: FileIdentity;
  hashes: FileHashes;
  capabilities: Capability[];
  sections: MetadataSection[];
  entropy: number;
  histogram: number[];
  parser_warnings: string[];
  metadata_size?: MetadataSizeInfo | null;
  duplicate_groups: DuplicateGroup[];
  missing_suggestions: MissingSuggestion[];
  appended_data?: { checked: boolean; trailing_bytes: number | null; note: string } | null;
}

export interface UploadResponse {
  file_id: string;
  analysis: AnalysisResult;
}

export interface PendingEdit {
  field_key: string;
  group: string;
  action: "set" | "remove";
  new_value?: unknown;
}

export interface CustomTimestamps {
  created?: string;
  modified?: string;
  accessed?: string;
}

export interface FieldDiffRecord {
  key: string;
  old_value: unknown;
  new_value: unknown;
  action: "set" | "remove";
}

export interface StreamPreservationReport {
  measured: boolean;
  method: string;
  preserved: boolean | null;
  before_hash?: string;
  after_hash?: string;
  note: string;
}

export interface SaveAsResponse {
  output_file_id: string;
  output_filename: string;
  output_hashes: FileHashes;
  applied_edits: Record<string, unknown>[];
  unsupported_edits: Record<string, unknown>[];
  failed_edits: Record<string, unknown>[];
  verification: Record<string, unknown> & {
    stream_preservation?: StreamPreservationReport;
    timestamp_report?: { notes?: string[] };
    hash_changed_from_working_copy?: boolean;
  };
  field_diffs: FieldDiffRecord[];
}

// ------------------------------------------------------------- snapshots --
export interface MetadataSnapshot {
  snapshot_id: string;
  label: string;
  created_at: string;
  field_map: Record<string, unknown>;
}

export interface DiffEntry {
  key: string;
  label?: string | null;
  before: unknown;
  after: unknown;
}

export interface MetadataDiff {
  added: DiffEntry[];
  removed: DiffEntry[];
  modified: DiffEntry[];
  baseline_label: string;
}

// ------------------------------------------------------- copy & paste -----
export interface CopyFieldResult {
  key: string;
  label: string;
  value: unknown;
  compatible: boolean;
  staged: boolean;
  reason?: string | null;
}

export interface CopyMetadataResponse {
  results: CopyFieldResult[];
  staged_count: number;
}

// ------------------------------------------------------------- presets ---
export interface PresetLogicalFields {
  author?: string | null;
  copyright?: string | null;
  title?: string | null;
  description?: string | null;
  keywords?: string | null;
}

export interface MetadataPreset {
  preset_id: string;
  name: string;
  fields: PresetLogicalFields;
  created_at: string;
}

export interface ApplyPresetResponse {
  staged: { logical_name: string; key: string; value: unknown }[];
  skipped: { logical_name: string; reason: string }[];
}

export interface RecentFile {
  file_id: string;
  original_filename: string;
  sanitized_filename: string;
  detected_format: string;
  mime_type: string;
  size_bytes: number;
  original_sha256: string;
  created_at: string;
  last_accessed_at: string;
  removed: number;
}

export interface OperationRecord {
  op_id: string;
  file_id: string;
  operation: string;
  fields_changed: string[];
  original_hash: string | null;
  output_hash: string | null;
  output_file_id: string | null;
  tool_versions: Record<string, unknown>;
  success: number;
  verification: Record<string, unknown> & { stream_preservation?: StreamPreservationReport };
  timestamp: string;
  field_diffs: FieldDiffRecord[];
}

export interface SystemStatus {
  app_name: string;
  app_version: string;
  app_author?: string;
  host: string;
  port: number;
  max_upload_bytes: number;
  tools: { name: string; available: boolean; path: string | null; version: string | null }[];
}
