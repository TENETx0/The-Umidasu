import { useEffect, useState } from "react";
import { api, ApiError } from "../services/api";
import type { MetadataSnapshot } from "../types/metadata";

export function SnapshotsPanel({
  fileId,
  onRestored,
}: {
  fileId: string;
  onRestored: (entries: { key: string; action: "set" | "remove"; value?: unknown }[]) => void;
}) {
  const [snapshots, setSnapshots] = useState<MetadataSnapshot[]>([]);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = async () => {
    try {
      setSnapshots(await api.listSnapshots(fileId));
    } catch {
      /* non-fatal */
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileId]);

  const takeSnapshot = async () => {
    setBusy(true);
    setMessage(null);
    try {
      await api.createSnapshot(fileId, label.trim() || undefined);
      setLabel("");
      await load();
      setMessage("Snapshot captured.");
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : "Failed to take snapshot");
    } finally {
      setBusy(false);
    }
  };

  const restore = async (snapshotId: string) => {
    setBusy(true);
    setMessage(null);
    try {
      const res = (await api.restoreSnapshot(fileId, snapshotId)) as unknown as {
        pending_count: number;
        pending: { key: string; action: "set" | "remove"; value?: unknown }[];
      };
      onRestored(res.pending ?? []);
      setMessage(`Restored — ${res.pending_count} field(s) staged. Review and Save As to write them.`);
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : "Failed to restore snapshot");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (snapshotId: string) => {
    setBusy(true);
    try {
      await api.deleteSnapshot(fileId, snapshotId);
      await load();
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : "Failed to delete snapshot");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card p-5">
      <h3 className="mb-1 text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">One-Click Metadata Snapshot</h3>
      <p className="mb-3 text-xs text-[var(--color-grey-400)]">
        Save the current writable metadata state so you can restore it later, even after further edits or a removal
        preset. An "Original" snapshot is captured automatically on upload.
      </p>

      <div className="mb-3 flex items-center gap-2">
        <input
          type="text"
          placeholder="Label (optional)"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className="flex-1 rounded-lg border border-[var(--color-border-strong)] px-3 py-1.5 text-sm outline-none focus:border-[var(--color-orange-400)]"
        />
        <button className="btn-primary rounded-lg px-3 py-1.5 text-sm" onClick={takeSnapshot} disabled={busy} type="button">
          Take Snapshot
        </button>
      </div>

      <ul className="flex flex-col gap-2">
        {snapshots.map((s) => (
          <li key={s.snapshot_id} className="flex items-center justify-between gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm">
            <div className="min-w-0">
              <p className="truncate font-medium text-[var(--color-ink)]">{s.label}</p>
              <p className="text-[11px] text-[var(--color-grey-400)]">
                {new Date(s.created_at).toLocaleString()} · {Object.keys(s.field_map).length} field(s)
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <button className="btn-secondary rounded px-2 py-1 text-xs" onClick={() => restore(s.snapshot_id)} disabled={busy} type="button">
                Restore
              </button>
              <button
                className="text-xs text-[var(--color-grey-400)] hover:text-[var(--color-danger)]"
                onClick={() => remove(s.snapshot_id)}
                disabled={busy}
                type="button"
              >
                ✕
              </button>
            </div>
          </li>
        ))}
        {snapshots.length === 0 && <p className="text-sm text-[var(--color-grey-400)]">No snapshots yet.</p>}
      </ul>
      {message && <p className="mt-2 text-xs text-[var(--color-grey-500)]">{message}</p>}
    </div>
  );
}
