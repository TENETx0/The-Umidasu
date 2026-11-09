import type { DuplicateGroup } from "../types/metadata";

function valueToText(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function DuplicatesPanel({ groups }: { groups: DuplicateGroup[] }) {
  if (groups.length === 0) {
    return (
      <div className="card p-5">
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">Duplicate Metadata Detector</h3>
        <p className="text-sm text-[var(--color-grey-500)]">
          No redundant or conflicting fields detected across namespaces (EXIF/IPTC/XMP/core properties).
        </p>
      </div>
    );
  }

  return (
    <div className="card p-5">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">Duplicate Metadata Detector</h3>
      <p className="mb-3 text-xs text-[var(--color-grey-400)]">
        Fields that express the same real-world concept (author, copyright, dates, …) across different tag
        namespaces. "Conflicting" means the values actually disagree — often a sign of edits made with different
        tools at different times.
      </p>
      <div className="flex flex-col gap-3">
        {groups.map((g) => (
          <div key={g.concept} className="rounded-lg border border-[var(--color-border)] p-3">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-sm font-medium text-[var(--color-ink)]">{g.concept}</span>
              <span
                className={`badge ${
                  g.status === "conflicting" ? "bg-[var(--color-danger-bg)] text-[var(--color-danger)]" : "bg-[var(--color-mist)] text-[var(--color-grey-600)]"
                }`}
              >
                {g.status}
              </span>
            </div>
            <ul className="flex flex-col gap-1">
              {g.fields.map((f) => (
                <li key={f.key} className="flex items-center justify-between gap-2 text-xs">
                  <span className="mono text-[var(--color-grey-500)]">{f.key}</span>
                  <span className="text-[var(--color-ink-soft)]">{valueToText(f.value)}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
