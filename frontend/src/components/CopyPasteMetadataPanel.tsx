import { useState } from "react";
import { api, ApiError } from "../services/api";
import type { CopyFieldResult, RecentFile } from "../types/metadata";

function valueToText(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function CopyPasteMetadataPanel({
  fileId,
  recentFiles,
  onStaged,
}: {
  fileId: string;
  recentFiles: RecentFile[];
  onStaged: (entries: { key: string; value: unknown }[]) => void;
}) {
  const [sourceId, setSourceId] = useState("");
  const [results, setResults] = useState<CopyFieldResult[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const otherFiles = recentFiles.filter((f) => f.file_id !== fileId && !f.removed);

  const run = async () => {
    if (!sourceId) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.copyMetadata(fileId, sourceId);
      setResults(res.results);
      const staged = res.results.filter((r) => r.staged).map((r) => ({ key: r.key, value: r.value }));
      if (staged.length > 0) onStaged(staged);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Copy failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card p-5">
      <h3 className="mb-1 text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">Metadata Copy &amp; Paste</h3>
      <p className="mb-3 text-xs text-[var(--color-grey-400)]">
        Copy writable metadata from another analyzed file onto this one. Only fields compatible with this file's
        format (image/media, Office, or PDF) are staged — everything else is listed with the reason it was skipped.
      </p>
      <div className="mb-3 flex items-center gap-2">
        <select
          value={sourceId}
          onChange={(e) => setSourceId(e.target.value)}
          className="flex-1 rounded-lg border border-[var(--color-border-strong)] px-3 py-1.5 text-sm outline-none focus:border-[var(--color-orange-400)]"
        >
          <option value="">Select a source file…</option>
          {otherFiles.map((f) => (
            <option key={f.file_id} value={f.file_id}>
              {f.original_filename} ({f.detected_format})
            </option>
          ))}
        </select>
        <button className="btn-primary rounded-lg px-3 py-1.5 text-sm" onClick={run} disabled={busy || !sourceId} type="button">
          {busy ? "Copying…" : "Copy Compatible Fields"}
        </button>
      </div>
      {error && <p className="mb-2 text-sm text-[var(--color-danger)]">{error}</p>}
      {results && (
        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium text-[var(--color-grey-500)]">
            {results.filter((r) => r.staged).length} of {results.length} field(s) staged as pending edits.
          </p>
          {results.map((r) => (
            <div
              key={r.key}
              className={`flex items-center justify-between gap-2 rounded px-2 py-1 text-xs ${
                r.staged ? "bg-[var(--color-success-bg)]" : "bg-[var(--color-mist)]"
              }`}
            >
              <span className="mono truncate">{r.key}</span>
              <span className="truncate text-[var(--color-ink-soft)]">{valueToText(r.value)}</span>
              <span className={r.staged ? "text-[var(--color-success)]" : "text-[var(--color-grey-400)]"}>
                {r.staged ? "staged" : r.reason ?? "skipped"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
