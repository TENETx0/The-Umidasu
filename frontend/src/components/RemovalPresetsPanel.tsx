import { useState } from "react";
import { api, ApiError } from "../services/api";
import type { AnalysisResult, SaveAsResponse } from "../types/metadata";

const PRESETS: { id: string; label: string; description: string }[] = [
  { id: "gps", label: "GPS / Location", description: "Removes GPS coordinates, altitude, and direction tags." },
  { id: "camera", label: "Camera / Device", description: "Removes make, model, lens, and serial number tags." },
  { id: "author", label: "Personal / Author", description: "Removes artist, creator, owner, and copyright tags." },
  { id: "timestamps", label: "Timestamps", description: "Removes embedded capture/creation/modify date tags." },
  { id: "comments", label: "Comments / Descriptions", description: "Removes user comments and description tags." },
  { id: "xmp_iptc", label: "XMP / IPTC", description: "Removes all XMP and IPTC metadata blocks." },
  { id: "all_writable", label: "All Writable Metadata", description: "Removes everything the active tool can safely write." },
];

export function RemovalPresetsPanel({
  fileId,
  onApplied,
  onSaved,
}: {
  fileId: string;
  onApplied: (analysis: AnalysisResult) => void;
  onSaved: (res: SaveAsResponse) => void;
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [applying, setApplying] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const apply = async () => {
    if (selected.size === 0) return;
    setApplying(true);
    setResult(null);
    try {
      const res = await api.applyRemovalPreset(fileId, Array.from(selected));
      onApplied(res.analysis);
      setResult("Presets applied to the working copy. Use Save Sanitized File below to export it.");
      setSelected(new Set());
    } catch (e) {
      setResult(e instanceof Error ? e.message : "Failed to apply preset");
    } finally {
      setApplying(false);
    }
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
    <div className="card p-5">
      <h3 className="mb-1 text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">
        Metadata Removal &amp; Sanitization
      </h3>
      <p className="mb-3 text-xs text-[var(--color-grey-400)]">
        Presets apply directly to the working copy. Some data may remain in pixels, document content, embedded
        streams, thumbnails, signatures, or format-specific structures that are not writable tags.
      </p>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {PRESETS.map((p) => (
          <label
            key={p.id}
            className={`flex cursor-pointer items-start gap-2 rounded-lg border px-3 py-2 text-sm transition-colors ${
              selected.has(p.id) ? "border-[var(--color-orange-400)] bg-[var(--color-orange-50)]" : "border-[var(--color-border)]"
            }`}
          >
            <input type="checkbox" className="mt-0.5" checked={selected.has(p.id)} onChange={() => toggle(p.id)} />
            <span>
              <span className="block font-medium text-[var(--color-ink)]">{p.label}</span>
              <span className="block text-xs text-[var(--color-grey-500)]">{p.description}</span>
            </span>
          </label>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-3">
        <button
          className="btn-primary rounded-lg px-4 py-1.5 text-sm font-medium"
          onClick={apply}
          disabled={applying || selected.size === 0}
          type="button"
        >
          {applying ? "Applying…" : `Apply ${selected.size || ""} Preset${selected.size === 1 ? "" : "s"}`.trim()}
        </button>
        {result && <p className="text-sm text-[var(--color-grey-500)]">{result}</p>}
      </div>

      <div className="mt-4 flex items-center justify-between gap-3 border-t border-[var(--color-border)] pt-4">
        <p className="text-xs text-[var(--color-grey-400)]">
          Save the working copy as a new, sanitized file — independent of applying presets above.
        </p>
        <button className="btn-primary shrink-0 rounded-lg px-4 py-1.5 text-sm font-medium" onClick={handleSave} disabled={saving} type="button">
          {saving ? "Saving…" : "Save Sanitized File"}
        </button>
      </div>
      {saveError && <p className="mt-2 text-sm text-[var(--color-danger)]">{saveError}</p>}
    </div>
  );
}
