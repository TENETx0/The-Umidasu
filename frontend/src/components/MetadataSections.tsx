import { useMemo, useState } from "react";
import type { AnalysisResult, MetadataField } from "../types/metadata";
import { StatusBadge } from "./StatusBadge";

function valueToText(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

const DIFF_STYLES: Record<string, string> = {
  added: "border-l-4 border-l-[var(--color-success)] bg-[var(--color-success-bg)]",
  removed: "border-l-4 border-l-[var(--color-danger)] bg-[var(--color-danger-bg)]",
  modified: "border-l-4 border-l-[var(--color-orange-400)] bg-[var(--color-orange-50)]",
};

const DIFF_LABELS: Record<string, string> = { added: "added", removed: "removed", modified: "modified" };

function CopyButton({ text, small }: { text: string; small?: boolean }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className={`text-[var(--color-orange-600)] hover:underline ${small ? "text-[11px]" : "text-xs"}`}
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1000);
      }}
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function FieldRow({ field, onStage }: { field: MetadataField; onStage: (f: MetadataField) => void }) {
  const diffClass = field.diff_status ? DIFF_STYLES[field.diff_status] ?? "" : "";
  return (
    <div
      className={`grid grid-cols-[1fr_1.4fr_auto] items-start gap-3 border-b border-[var(--color-border)] py-2 text-sm last:border-0 ${diffClass}`}
    >
      <div className="min-w-0">
        <p className="truncate font-medium text-[var(--color-ink)]">{field.label}</p>
        <p className="mono truncate text-[11px] text-[var(--color-grey-400)]">{field.key}</p>
        <div className="mt-1 flex flex-wrap gap-1">
          {field.sensitive && <span className="badge inline-block bg-[var(--color-danger-bg)] text-[var(--color-danger)]">sensitive</span>}
          {field.is_unknown_tag && (
            <span className="badge inline-block bg-[var(--color-grey-100)] text-[var(--color-grey-600)]" title="Not in the curated common-tag list">
              uncommon tag
            </span>
          )}
          {field.diff_status && (
            <span className="badge inline-block bg-[var(--color-mist)] text-[var(--color-ink-soft)]" style={{ border: "1px solid var(--color-border-strong)" }}>
              {DIFF_LABELS[field.diff_status]}
            </span>
          )}
        </div>
      </div>
      <div className="min-w-0">
        <p className="break-words text-[var(--color-ink-soft)]">{valueToText(field.normalized_value)}</p>
        {field.notes && <p className="mt-0.5 text-[11px] italic text-[var(--color-grey-400)]">{field.notes}</p>}

        {/* Unknown Tag Decoder detail */}
        {field.is_unknown_tag && (
          <p className="mt-1 text-[11px] text-[var(--color-grey-500)]">
            tag id: <span className="mono">{field.tag_id ?? "n/a"}</span> · namespace:{" "}
            <span className="mono">{field.namespace ?? "n/a"}</span> · type: <span className="mono">{field.value_type}</span>
          </p>
        )}

        {/* GPS Coordinate Converter */}
        {field.representations && (
          <div className="mt-1 flex flex-col gap-0.5 rounded bg-[var(--color-mist)] px-2 py-1">
            {Object.entries(field.representations).map(([repName, repValue]) => (
              <div key={repName} className="flex items-center justify-between gap-2 text-[11px]">
                <span className="text-[var(--color-grey-500)]">
                  {repName}: <span className="mono text-[var(--color-ink-soft)]">{repValue}</span>
                </span>
                <CopyButton text={repValue} small />
              </div>
            ))}
          </div>
        )}

        {/* Timestamp Normalizer */}
        {field.is_timestamp && (
          <p className="mt-1 text-[11px] text-[var(--color-grey-500)]">
            {field.timestamp_has_tz && field.timestamp_utc ? (
              <>
                UTC: <span className="mono text-[var(--color-ink-soft)]">{field.timestamp_utc}</span> (original value shown above,
                carries explicit timezone)
              </>
            ) : (
              <span className="italic">No timezone offset in the source value — shown as-is, not converted (never guessed).</span>
            )}
          </p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <CopyButton text={valueToText(field.normalized_value)} />
        {field.writable && (
          <button type="button" className="btn-secondary rounded px-2 py-1 text-xs" onClick={() => onStage(field)}>
            Edit
          </button>
        )}
      </div>
    </div>
  );
}

export function MetadataSections({
  analysis,
  onStageEdit,
  diffMap,
}: {
  analysis: AnalysisResult;
  onStageEdit: (f: MetadataField) => void;
  /** Metadata Difference Highlighting: key -> added/removed/modified,
   * computed by the caller from a /diff response plus the removed-only
   * keys (which don't appear in `analysis.sections` at all). */
  diffMap?: Record<string, "added" | "removed" | "modified">;
}) {
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set(analysis.sections.filter((s) => s.fields.length > 0).map((s) => s.section_id)));
  const [onlyEditable, setOnlyEditable] = useState(false);
  const [onlySensitive, setOnlySensitive] = useState(false);
  const [onlyUnknown, setOnlyUnknown] = useState(false);

  const q = query.trim().toLowerCase();

  const filteredSections = useMemo(() => {
    return analysis.sections.map((s) => {
      const fields = s.fields
        .filter((f) => {
          if (onlyEditable && !f.writable) return false;
          if (onlySensitive && !f.sensitive) return false;
          if (onlyUnknown && !f.is_unknown_tag) return false;
          if (!q) return true;
          // Metadata Search Everywhere: match label, key, normalized AND
          // raw value (raw can differ from normalized, e.g. struct/array
          // tags), so a search really is exhaustive across every field.
          return (
            f.label.toLowerCase().includes(q) ||
            f.key.toLowerCase().includes(q) ||
            valueToText(f.normalized_value).toLowerCase().includes(q) ||
            valueToText(f.raw_value).toLowerCase().includes(q) ||
            (f.namespace ?? "").toLowerCase().includes(q) ||
            (f.tag_id ?? "").toLowerCase().includes(q)
          );
        })
        .map((f) => (diffMap?.[f.key] ? { ...f, diff_status: diffMap[f.key] } : f));
      return { ...s, fields };
    });
  }, [analysis.sections, q, onlyEditable, onlySensitive, onlyUnknown, diffMap]);

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const expandAll = () => setExpanded(new Set(analysis.sections.map((s) => s.section_id)));
  const collapseAll = () => setExpanded(new Set());

  return (
    <div className="card p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">Metadata &amp; Technical Analysis</h3>
        <div className="flex items-center gap-2 text-xs">
          <button className="btn-secondary rounded px-2 py-1" onClick={expandAll} type="button">
            Expand all
          </button>
          <button className="btn-secondary rounded px-2 py-1" onClick={collapseAll} type="button">
            Collapse all
          </button>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          type="text"
          placeholder="Search all extracted fields…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-64 rounded-lg border border-[var(--color-border-strong)] px-3 py-1.5 text-sm outline-none focus:border-[var(--color-orange-400)]"
        />
        <label className="flex items-center gap-1 text-xs text-[var(--color-grey-500)]">
          <input type="checkbox" checked={onlyEditable} onChange={(e) => setOnlyEditable(e.target.checked)} />
          Editable only
        </label>
        <label className="flex items-center gap-1 text-xs text-[var(--color-grey-500)]">
          <input type="checkbox" checked={onlySensitive} onChange={(e) => setOnlySensitive(e.target.checked)} />
          Sensitive only
        </label>
        <label className="flex items-center gap-1 text-xs text-[var(--color-grey-500)]">
          <input type="checkbox" checked={onlyUnknown} onChange={(e) => setOnlyUnknown(e.target.checked)} />
          Uncommon tags only
        </label>
      </div>

      {diffMap && Object.values(diffMap).includes("removed") && (
        <div className="mb-3 rounded-lg border border-[var(--color-danger)] bg-[var(--color-danger-bg)] px-3 py-2 text-xs text-[var(--color-danger)]">
          <p className="font-medium">Removed since baseline:</p>
          {Object.entries(diffMap)
            .filter(([, status]) => status === "removed")
            .map(([key]) => (
              <span key={key} className="mono mr-2 inline-block">
                {key}
              </span>
            ))}
        </div>
      )}

      <div className="flex flex-col gap-2">
        {filteredSections.map((s) => {
          const isOpen = expanded.has(s.section_id);
          const hasFields = s.fields.length > 0;
          return (
            <div key={s.section_id} className="rounded-lg border border-[var(--color-border)]">
              <button
                type="button"
                onClick={() => toggle(s.section_id)}
                className="flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left hover:bg-[var(--color-mist)]"
              >
                <span className="flex items-center gap-2 text-sm font-medium text-[var(--color-ink)]">
                  <span className={`inline-block transition-transform ${isOpen ? "rotate-90" : ""}`}>›</span>
                  {s.title}
                  <span className="text-xs font-normal text-[var(--color-grey-400)]">({s.fields.length})</span>
                </span>
                <StatusBadge status={s.status} />
              </button>
              {isOpen && (
                <div className="border-t border-[var(--color-border)] px-3 py-2">
                  {s.detail_message && <p className="mb-2 text-xs italic text-[var(--color-grey-500)]">{s.detail_message}</p>}
                  {s.warnings.map((w, i) => (
                    <p key={i} className="mb-2 rounded bg-[var(--color-orange-50)] px-2 py-1 text-xs text-[var(--color-orange-700)]">
                      ⚠ {w}
                    </p>
                  ))}
                  {hasFields ? (
                    s.fields.map((f) => <FieldRow key={f.key} field={f} onStage={onStageEdit} />)
                  ) : (
                    <p className="py-2 text-xs text-[var(--color-grey-400)]">No fields match the current filters.</p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
