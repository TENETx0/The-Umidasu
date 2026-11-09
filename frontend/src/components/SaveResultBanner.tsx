import { api } from "../services/api";
import type { SaveAsResponse } from "../types/metadata";

function valueToText(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function SaveResultBanner({
  fileId,
  result,
  onDismiss,
}: {
  fileId: string;
  result: SaveAsResponse;
  onDismiss: () => void;
}) {
  const verification = result.verification;
  const sp = verification.stream_preservation;
  return (
    <div className="card border-[var(--color-orange-300)] bg-[var(--color-orange-50)] p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-[var(--color-orange-700)]">Save complete — {result.output_filename}</h3>
          <p className="mt-1 text-xs text-[var(--color-grey-500)]">
            Applied {result.applied_edits.length} edit(s). {result.failed_edits.length > 0 && `${result.failed_edits.length} failed.`}{" "}
            {result.unsupported_edits.length > 0 && `${result.unsupported_edits.length} unsupported.`}
          </p>
          <p className="mono mt-1 break-all text-[11px] text-[var(--color-grey-400)]">sha256: {result.output_hashes.sha256}</p>
          {verification.hash_changed_from_working_copy !== undefined && (
            <p className="mt-1 text-xs text-[var(--color-grey-500)]">
              Output hash differs from pre-edit copy: {verification.hash_changed_from_working_copy ? "Yes" : "No"}
            </p>
          )}
          {verification.timestamp_report?.notes?.map((n, i) => (
            <p key={i} className="mt-1 text-[11px] italic text-[var(--color-grey-500)]">
              {n}
            </p>
          ))}

          {/* Save Without Recompression (feature #15) */}
          {sp && (
            <p
              className={`mt-1 text-xs font-medium ${
                sp.preserved === true ? "text-[var(--color-success)]" : sp.preserved === false ? "text-[var(--color-danger)]" : "text-[var(--color-grey-500)]"
              }`}
            >
              {sp.preserved === true ? "✓ " : sp.preserved === false ? "✗ " : ""}
              {sp.note}
            </p>
          )}
        </div>
        <button className="text-sm text-[var(--color-grey-400)] hover:text-[var(--color-ink)]" onClick={onDismiss} type="button">
          ✕
        </button>
      </div>
      <a
        href={api.downloadUrl(fileId, result.output_file_id)}
        download={result.output_filename}
        className="btn-primary mt-3 inline-block rounded-lg px-4 py-1.5 text-sm font-medium"
      >
        Download {result.output_filename}
      </a>

      {/* Metadata Change History (feature #13) */}
      {result.field_diffs.length > 0 && (
        <div className="mt-3 border-t border-[var(--color-orange-200)] pt-3 text-xs">
          <p className="mb-1 font-medium text-[var(--color-ink)]">Changes applied:</p>
          {result.field_diffs.map((d) => (
            <p key={d.key} className="mono text-[11px] text-[var(--color-grey-600)]">
              {d.key}: {d.action === "remove" ? "removed" : `${valueToText(d.old_value)} → ${valueToText(d.new_value)}`}
            </p>
          ))}
        </div>
      )}

      {(result.failed_edits.length > 0 || result.unsupported_edits.length > 0) && (
        <div className="mt-3 border-t border-[var(--color-orange-200)] pt-3 text-xs">
          {result.failed_edits.map((e, i) => (
            <p key={i} className="text-[var(--color-danger)]">
              Failed: {String(e.field_key)} — {String(e.reason)}
            </p>
          ))}
          {result.unsupported_edits.map((e, i) => (
            <p key={i} className="text-[var(--color-grey-500)]">
              Unsupported: {String(e.field_key)} — {String(e.reason)}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
