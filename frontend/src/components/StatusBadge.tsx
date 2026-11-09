import type { ExtractionStatus } from "../types/metadata";

const STYLES: Record<ExtractionStatus, string> = {
  extracted_successfully: "bg-[var(--color-orange-100)] text-[var(--color-orange-700)]",
  no_relevant_metadata_found: "bg-[var(--color-grey-100)] text-[var(--color-grey-500)]",
  not_supported_for_this_format: "bg-[var(--color-grey-100)] text-[var(--color-grey-400)]",
  extraction_failed: "bg-[var(--color-danger-bg)] text-[var(--color-danger)]",
  not_analyzed: "bg-[var(--color-grey-100)] text-[var(--color-grey-400)]",
};

const LABELS: Record<ExtractionStatus, string> = {
  extracted_successfully: "Extracted",
  no_relevant_metadata_found: "No metadata found",
  not_supported_for_this_format: "Not supported",
  extraction_failed: "Extraction failed",
  not_analyzed: "Not analyzed",
};

export function StatusBadge({ status }: { status: ExtractionStatus }) {
  return <span className={`badge ${STYLES[status]}`}>{LABELS[status]}</span>;
}
