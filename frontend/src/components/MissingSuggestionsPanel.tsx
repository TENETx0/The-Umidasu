import type { MissingSuggestion } from "../types/metadata";

export function MissingSuggestionsPanel({ suggestions }: { suggestions: MissingSuggestion[] }) {
  if (suggestions.length === 0) return null;

  return (
    <div className="card p-5">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">Missing Metadata Suggestions</h3>
      <p className="mb-3 text-xs text-[var(--color-grey-400)]">
        Fields commonly populated on files like this one, but absent here. Purely informational — plenty of
        legitimate files never had these set.
      </p>
      <ul className="flex flex-col gap-2">
        {suggestions.map((s) => (
          <li key={s.logical_name} className="rounded-lg border border-[var(--color-border)] p-3 text-sm">
            <p className="font-medium text-[var(--color-ink)]">{s.logical_name}</p>
            <p className="mt-0.5 text-xs text-[var(--color-grey-500)]">{s.note}</p>
            <p className="mono mt-1 text-[11px] text-[var(--color-grey-400)]">candidates: {s.candidate_keys.join(", ")}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
