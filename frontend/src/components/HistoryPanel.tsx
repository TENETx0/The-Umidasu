import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { OperationRecord } from "../types/metadata";

function valueToText(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function HistoryPanel({ fileId }: { fileId: string }) {
  const [ops, setOps] = useState<OperationRecord[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setOps(await api.getHistory(fileId));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileId]);

  return (
    <div className="card p-5">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">Operation History</h3>
        <button type="button" className="text-xs text-[var(--color-orange-600)] hover:underline" onClick={load}>
          Refresh
        </button>
      </div>
      {loading && <p className="text-sm text-[var(--color-grey-400)]">Loading…</p>}
      {!loading && ops.length === 0 && <p className="text-sm text-[var(--color-grey-400)]">No save operations recorded yet.</p>}
      <ul className="flex flex-col gap-2">
        {ops.map((op) => (
          <li key={op.op_id} className="rounded-lg border border-[var(--color-border)] p-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="font-medium">{op.operation}</span>
              <span className={`badge ${op.success ? "bg-[var(--color-orange-100)] text-[var(--color-orange-700)]" : "bg-[var(--color-danger-bg)] text-[var(--color-danger)]"}`}>
                {op.success ? "success" : "failure"}
              </span>
            </div>
            <p className="mt-1 text-xs text-[var(--color-grey-400)]">{new Date(op.timestamp).toLocaleString()}</p>
            <p className="mt-1 text-xs text-[var(--color-grey-500)]">Fields changed: {op.fields_changed.join(", ") || "none"}</p>
            <p className="mono mt-1 break-all text-[11px] text-[var(--color-grey-400)]">output hash: {op.output_hash}</p>

            {/* Metadata Change History (feature #13) */}
            {op.field_diffs && op.field_diffs.length > 0 && (
              <div className="mt-2 flex flex-col gap-1 border-t border-[var(--color-border)] pt-2">
                {op.field_diffs.map((d) => (
                  <div key={d.key} className="text-[11px]">
                    <span className="mono text-[var(--color-grey-500)]">{d.key}</span>:{" "}
                    {d.action === "remove" ? (
                      <span className="text-[var(--color-danger)]">removed (was {valueToText(d.old_value)})</span>
                    ) : (
                      <>
                        <span className="line-through text-[var(--color-grey-400)]">{valueToText(d.old_value)}</span>{" "}
                        → <span className="font-medium text-[var(--color-ink)]">{valueToText(d.new_value)}</span>
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Save Without Recompression (feature #15) */}
            {op.verification?.stream_preservation && (
              <p
                className={`mt-2 text-[11px] ${
                  op.verification.stream_preservation.preserved === true
                    ? "text-[var(--color-success)]"
                    : op.verification.stream_preservation.preserved === false
                      ? "text-[var(--color-danger)]"
                      : "text-[var(--color-grey-400)]"
                }`}
              >
                Stream preservation: {op.verification.stream_preservation.note}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
