import { useState } from "react";
import { api, ApiError } from "../services/api";
import type { MetadataField, SaveAsResponse } from "../types/metadata";
import type { PendingEditState } from "../hooks/useFileSession";

export function MetadataEditor({
  fileId,
  pending,
  stagedField,
  onClearStaged,
  onApplyEdit,
  onClearEdit,
  onUndo,
  onRedo,
  onReset,
  onRevert,
  onSaved,
}: {
  fileId: string;
  pending: PendingEditState;
  stagedField: MetadataField | null;
  onClearStaged: () => void;
  onApplyEdit: (fieldKey: string, group: string, action: "set" | "remove", value?: unknown) => Promise<void>;
  onClearEdit: (fieldKey: string) => Promise<void>;
  onUndo: () => Promise<void>;
  onRedo: () => Promise<void>;
  onReset: () => Promise<void>;
  onRevert: () => Promise<void>;
  onSaved: (res: SaveAsResponse) => void;
}) {
  const [draftValue, setDraftValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const pendingEntries = Object.entries(pending);

  const commitDraft = async () => {
    if (!stagedField) return;
    await onApplyEdit(stagedField.key, stagedField.group, "set", draftValue);
    setDraftValue("");
    onClearStaged();
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const res = await api.saveAs(fileId);
      onSaved(res);
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card p-5" id="metadata-editor">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">Metadata Editor</h3>

      {stagedField && (
        <div className="mb-4 rounded-lg border border-[var(--color-orange-200)] bg-[var(--color-orange-50)] p-3">
          <p className="mb-1 text-sm font-medium text-[var(--color-ink)]">Editing: {stagedField.label}</p>
          <p className="mono mb-2 text-[11px] text-[var(--color-grey-500)]">{stagedField.key}</p>
          <p className="mb-2 text-xs text-[var(--color-grey-500)]">
            Current value: <span className="font-medium text-[var(--color-ink)]">{String(stagedField.normalized_value ?? "—")}</span>
          </p>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={draftValue}
              onChange={(e) => setDraftValue(e.target.value)}
              placeholder="New value"
              className="flex-1 rounded-lg border border-[var(--color-border-strong)] px-3 py-1.5 text-sm outline-none focus:border-[var(--color-orange-400)]"
            />
            <button className="btn-primary rounded-lg px-3 py-1.5 text-sm" onClick={commitDraft} type="button">
              Stage Edit
            </button>
            <button
              className="btn-secondary rounded-lg px-3 py-1.5 text-sm"
              onClick={() => onApplyEdit(stagedField.key, stagedField.group, "remove").then(onClearStaged)}
              type="button"
            >
              Remove Field
            </button>
            <button className="text-sm text-[var(--color-grey-500)] hover:underline" onClick={onClearStaged} type="button">
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="mb-4">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--color-grey-400)]">
          Pending changes ({pendingEntries.length})
        </p>
        {pendingEntries.length === 0 ? (
          <p className="text-sm text-[var(--color-grey-400)]">No pending edits. Click "Edit" on a writable field above to stage a change.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {pendingEntries.map(([key, v]) => (
              <li key={key} className="flex items-center justify-between gap-2 rounded-lg bg-[var(--color-mist)] px-3 py-1.5 text-sm">
                <span className="mono truncate text-xs">{key}</span>
                <span className="shrink-0 text-[var(--color-ink-soft)]">
                  {v.action === "remove" ? <em className="text-[var(--color-danger)]">remove</em> : String(v.value)}
                </span>
                <button
                  type="button"
                  className="shrink-0 text-xs text-[var(--color-grey-400)] hover:text-[var(--color-danger)]"
                  onClick={() => onClearEdit(key)}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-[var(--color-border)] pt-4">
        <button className="btn-secondary rounded-lg px-3 py-1.5 text-sm" onClick={onUndo} type="button">
          Undo
        </button>
        <button className="btn-secondary rounded-lg px-3 py-1.5 text-sm" onClick={onRedo} type="button">
          Redo
        </button>
        <button className="btn-secondary rounded-lg px-3 py-1.5 text-sm" onClick={onReset} type="button">
          Reset Pending Changes
        </button>
        <button
          className="btn-secondary rounded-lg px-3 py-1.5 text-sm"
          onClick={() => {
            if (confirm("Revert the working copy to the original file? This discards any applied removal presets.")) onRevert();
          }}
          type="button"
        >
          Revert Working Copy
        </button>
        <div className="grow" />
        <button
          className="btn-primary rounded-lg px-4 py-1.5 text-sm font-medium"
          onClick={handleSave}
          disabled={saving || pendingEntries.length === 0}
          type="button"
        >
          {saving ? "Saving…" : "Save As New File"}
        </button>
      </div>
      {saveError && <p className="mt-2 text-sm text-[var(--color-danger)]">{saveError}</p>}
    </div>
  );
}
