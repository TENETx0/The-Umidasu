import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { MetadataDiff } from "../types/metadata";

function valueToText(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/** Metadata Difference Highlighting (feature #3). Diffs the current
 * (including unsaved pending edits) state against the earliest snapshot,
 * refreshing whenever `refreshKey` changes — pass something that changes
 * on every pending-edit mutation (e.g. the pending-edit count) so this
 * updates live as the user edits, not just after a save. */
export function DiffPanel({ fileId, refreshKey }: { fileId: string; refreshKey: unknown }) {
  const [diff, setDiff] = useState<MetadataDiff | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getDiff(fileId)
      .then((d) => {
        if (!cancelled) {
          setDiff(d);
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "No baseline snapshot yet");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileId, refreshKey]);

  if (error) {
    return (
      <div className="card p-5">
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">Metadata Difference Highlighting</h3>
        <p className="text-sm text-[var(--color-grey-400)]">{error}</p>
      </div>
    );
  }
  if (!diff) return null;

  const totalChanges = diff.added.length + diff.removed.length + diff.modified.length;

  return (
    <div className="card p-5">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">Metadata Difference Highlighting</h3>
        <span className="text-xs text-[var(--color-grey-400)]">vs. "{diff.baseline_label}"</span>
      </div>
      {totalChanges === 0 ? (
        <p className="text-sm text-[var(--color-grey-500)]">No differences from the baseline (including unsaved pending edits).</p>
      ) : (
        <div className="flex flex-col gap-3">
          {diff.added.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-semibold text-[var(--color-success)]">Added ({diff.added.length})</p>
              {diff.added.map((e) => (
                <div key={e.key} className="mono flex justify-between gap-2 border-l-4 border-l-[var(--color-success)] bg-[var(--color-success-bg)] px-2 py-1 text-xs">
                  <span>{e.key}</span>
                  <span>{valueToText(e.after)}</span>
                </div>
              ))}
            </div>
          )}
          {diff.removed.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-semibold text-[var(--color-danger)]">Removed ({diff.removed.length})</p>
              {diff.removed.map((e) => (
                <div key={e.key} className="mono flex justify-between gap-2 border-l-4 border-l-[var(--color-danger)] bg-[var(--color-danger-bg)] px-2 py-1 text-xs">
                  <span>{e.key}</span>
                  <span className="line-through">{valueToText(e.before)}</span>
                </div>
              ))}
            </div>
          )}
          {diff.modified.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-semibold text-[var(--color-orange-700)]">Modified ({diff.modified.length})</p>
              {diff.modified.map((e) => (
                <div key={e.key} className="border-l-4 border-l-[var(--color-orange-400)] bg-[var(--color-orange-50)] px-2 py-1 text-xs">
                  <p className="mono">{e.key}</p>
                  <p>
                    <span className="line-through">{valueToText(e.before)}</span> → <span className="font-medium">{valueToText(e.after)}</span>
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
