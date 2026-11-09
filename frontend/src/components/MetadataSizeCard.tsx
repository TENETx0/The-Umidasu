import type { MetadataSizeInfo } from "../types/metadata";

export function MetadataSizeCard({ info }: { info: MetadataSizeInfo | null | undefined }) {
  if (!info) return null;

  if (!info.measured) {
    return (
      <div className="card p-5">
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">Metadata Size Analyzer</h3>
        <p className="text-sm text-[var(--color-grey-500)]">{info.note ?? "Not measurable for this format."}</p>
      </div>
    );
  }

  const pct = Math.min(100, Math.max(0, info.percentage));
  return (
    <div className="card p-5">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">Metadata Size Analyzer</h3>
      <div className="mb-2 flex items-baseline justify-between">
        <span className="text-2xl font-semibold text-[var(--color-orange-600)]">{pct.toFixed(2)}%</span>
        <span className="text-xs text-[var(--color-grey-500)]">
          {info.metadata_bytes.toLocaleString()} of {info.total_bytes.toLocaleString()} bytes
        </span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-[var(--color-mist)]">
        <div className="h-full rounded-full bg-[var(--color-orange-500)]" style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-2 text-[11px] text-[var(--color-grey-400)]">
        Method: <span className="mono">{info.method}</span> — measured by direct structural parsing, not estimated.
      </p>
      {info.note && <p className="mt-1 text-[11px] italic text-[var(--color-grey-400)]">{info.note}</p>}
    </div>
  );
}
