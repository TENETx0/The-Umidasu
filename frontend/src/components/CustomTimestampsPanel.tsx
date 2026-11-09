import { useState } from "react";
import { api } from "../services/api";

export function CustomTimestampsPanel({ fileId }: { fileId: string }) {
  const [created, setCreated] = useState("");
  const [modified, setModified] = useState("");
  const [accessed, setAccessed] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apply = async () => {
    setError(null);
    try {
      await api.setCustomTimestamps(fileId, {
        created: created ? new Date(created).toISOString() : undefined,
        modified: modified ? new Date(modified).toISOString() : undefined,
        accessed: accessed ? new Date(accessed).toISOString() : undefined,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to set timestamps");
    }
  };

  return (
    <div className="card p-5">
      <h3 className="mb-1 text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">Custom File Timestamps</h3>
      <p className="mb-3 text-xs text-[var(--color-grey-400)]">
        Set the output file's created, modified, and accessed dates. These apply when you Save As. Embedded date tags
        (EXIF/XMP/QuickTime) are also updated where the format supports it.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <label className="text-xs text-[var(--color-grey-500)]">
          Created
          <input
            type="datetime-local"
            value={created}
            onChange={(e) => setCreated(e.target.value)}
            className="mt-1 w-full rounded-lg border border-[var(--color-border-strong)] px-2 py-1.5 text-sm outline-none focus:border-[var(--color-orange-400)]"
          />
        </label>
        <label className="text-xs text-[var(--color-grey-500)]">
          Modified
          <input
            type="datetime-local"
            value={modified}
            onChange={(e) => setModified(e.target.value)}
            className="mt-1 w-full rounded-lg border border-[var(--color-border-strong)] px-2 py-1.5 text-sm outline-none focus:border-[var(--color-orange-400)]"
          />
        </label>
        <label className="text-xs text-[var(--color-grey-500)]">
          Accessed
          <input
            type="datetime-local"
            value={accessed}
            onChange={(e) => setAccessed(e.target.value)}
            className="mt-1 w-full rounded-lg border border-[var(--color-border-strong)] px-2 py-1.5 text-sm outline-none focus:border-[var(--color-orange-400)]"
          />
        </label>
      </div>
      <div className="mt-3 flex items-center gap-3">
        <button className="btn-primary rounded-lg px-4 py-1.5 text-sm font-medium" onClick={apply} type="button">
          {saved ? "Saved ✓" : "Apply to Next Save"}
        </button>
        <p className="text-[11px] italic text-[var(--color-grey-400)]">
          Note: on Linux, a file's filesystem "created" (birth) time cannot be set directly by any public API. The
          requested created date is written into embedded metadata instead, and this is reported after saving.
        </p>
      </div>
      {error && <p className="mt-2 text-sm text-[var(--color-danger)]">{error}</p>}
    </div>
  );
}
