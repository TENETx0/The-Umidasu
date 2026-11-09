import { useEffect, useState } from "react";
import { api, ApiError } from "../services/api";
import type { MetadataPreset, PresetLogicalFields } from "../types/metadata";

const LOGICAL_FIELDS: { key: keyof PresetLogicalFields; label: string }[] = [
  { key: "author", label: "Author" },
  { key: "copyright", label: "Copyright" },
  { key: "title", label: "Title" },
  { key: "description", label: "Description" },
  { key: "keywords", label: "Keywords" },
];

export function PresetsPanel({
  fileId,
  onApplied,
}: {
  fileId: string;
  onApplied: (entries: { key: string; value: unknown }[]) => void;
}) {
  const [presets, setPresets] = useState<MetadataPreset[]>([]);
  const [newName, setNewName] = useState("");
  const [newFields, setNewFields] = useState<PresetLogicalFields>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const load = async () => {
    try {
      setPresets(await api.listPresets());
    } catch {
      /* non-fatal */
    }
  };

  useEffect(() => {
    load();
  }, []);

  const createPreset = async () => {
    if (!newName.trim()) return;
    setBusy(true);
    try {
      await api.createPreset(newName.trim(), newFields);
      setNewName("");
      setNewFields({});
      setShowForm(false);
      await load();
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : "Failed to create preset");
    } finally {
      setBusy(false);
    }
  };

  const apply = async (presetId: string) => {
    setBusy(true);
    setMessage(null);
    try {
      const res = await api.applyPreset(fileId, presetId);
      if (res.staged.length > 0) onApplied(res.staged.map((s) => ({ key: s.key, value: s.value })));
      const skippedMsg = res.skipped.length > 0 ? ` Skipped: ${res.skipped.map((s) => `${s.logical_name} (${s.reason})`).join("; ")}` : "";
      setMessage(`Staged ${res.staged.length} field(s).${skippedMsg}`);
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : "Failed to apply preset");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (presetId: string) => {
    setBusy(true);
    try {
      await api.deletePreset(presetId);
      await load();
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : "Failed to delete preset");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card p-5">
      <div className="mb-1 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">Metadata Presets</h3>
        <button className="text-xs text-[var(--color-orange-600)] hover:underline" onClick={() => setShowForm((v) => !v)} type="button">
          {showForm ? "Cancel" : "+ New preset"}
        </button>
      </div>
      <p className="mb-3 text-xs text-[var(--color-grey-400)]">
        Reusable templates (author, copyright, title, description, keywords) mapped onto whichever concrete fields
        this file's format actually supports. Fields with no sensible analog in a given format are skipped, not
        force-mapped.
      </p>

      {showForm && (
        <div className="mb-3 rounded-lg border border-[var(--color-border)] p-3">
          <input
            type="text"
            placeholder="Preset name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="mb-2 w-full rounded-lg border border-[var(--color-border-strong)] px-3 py-1.5 text-sm outline-none focus:border-[var(--color-orange-400)]"
          />
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {LOGICAL_FIELDS.map((f) => (
              <input
                key={f.key}
                type="text"
                placeholder={f.label}
                value={newFields[f.key] ?? ""}
                onChange={(e) => setNewFields((prev) => ({ ...prev, [f.key]: e.target.value }))}
                className="rounded-lg border border-[var(--color-border-strong)] px-3 py-1.5 text-sm outline-none focus:border-[var(--color-orange-400)]"
              />
            ))}
          </div>
          <button className="btn-primary mt-2 rounded-lg px-3 py-1.5 text-sm" onClick={createPreset} disabled={busy} type="button">
            Save Preset
          </button>
        </div>
      )}

      <ul className="flex flex-col gap-2">
        {presets.map((p) => (
          <li key={p.preset_id} className="flex items-center justify-between gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm">
            <div className="min-w-0">
              <p className="truncate font-medium text-[var(--color-ink)]">{p.name}</p>
              <p className="truncate text-[11px] text-[var(--color-grey-400)]">
                {LOGICAL_FIELDS.filter((f) => p.fields[f.key])
                  .map((f) => f.label)
                  .join(", ") || "no fields set"}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <button className="btn-secondary rounded px-2 py-1 text-xs" onClick={() => apply(p.preset_id)} disabled={busy} type="button">
                Apply
              </button>
              <button
                className="text-xs text-[var(--color-grey-400)] hover:text-[var(--color-danger)]"
                onClick={() => remove(p.preset_id)}
                disabled={busy}
                type="button"
              >
                ✕
              </button>
            </div>
          </li>
        ))}
        {presets.length === 0 && !showForm && <p className="text-sm text-[var(--color-grey-400)]">No presets saved yet.</p>}
      </ul>
      {message && <p className="mt-2 text-xs text-[var(--color-grey-500)]">{message}</p>}
    </div>
  );
}
