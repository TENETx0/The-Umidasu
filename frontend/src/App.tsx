import { useCallback, useEffect, useMemo, useState } from "react";
import { CopyPasteMetadataPanel } from "./components/CopyPasteMetadataPanel";
import { CustomTimestampsPanel } from "./components/CustomTimestampsPanel";
import { DiffPanel } from "./components/DiffPanel";
import { DuplicatesPanel } from "./components/DuplicatesPanel";
import { FileIdentityCard } from "./components/FileIdentityCard";
import { Header } from "./components/Header";
import { HashesCard } from "./components/HashesCard";
import { HexViewer } from "./components/HexViewer";
import { HistoryPanel } from "./components/HistoryPanel";
import { InsertMetadataPanel } from "./components/InsertMetadataPanel";
import { MetadataEditor } from "./components/MetadataEditor";
import { MetadataSections } from "./components/MetadataSections";
import { MetadataSizeCard } from "./components/MetadataSizeCard";
import { MissingSuggestionsPanel } from "./components/MissingSuggestionsPanel";
import { PresetsPanel } from "./components/PresetsPanel";
import { RecentFilesList } from "./components/RecentFilesList";
import { RemovalPresetsPanel } from "./components/RemovalPresetsPanel";
import { ReportsPanel } from "./components/ReportsPanel";
import { SaveResultBanner } from "./components/SaveResultBanner";
import { SnapshotsPanel } from "./components/SnapshotsPanel";
import { UploadZone } from "./components/UploadZone";
import { useFileSession } from "./hooks/useFileSession";
import { api } from "./services/api";
import type { MetadataDiff, MetadataField, RecentFile, SaveAsResponse, SystemStatus, UploadResponse } from "./types/metadata";

type Tab = "inspect" | "editor" | "tools" | "cleanup" | "history";

function App() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [recentFiles, setRecentFiles] = useState<RecentFile[]>([]);
  const [stagedField, setStagedField] = useState<MetadataField | null>(null);
  const [saveResult, setSaveResult] = useState<SaveAsResponse | null>(null);
  const [tab, setTab] = useState<Tab>("inspect");

  const session = useFileSession();
  const [diff, setDiff] = useState<MetadataDiff | null>(null);

  const refreshRecent = useCallback(async () => {
    try {
      setRecentFiles(await api.listRecentFiles());
    } catch {
      /* non-fatal */
    }
  }, []);

  useEffect(() => {
    api.systemStatus().then(setStatus).catch(() => undefined);
    refreshRecent();
  }, [refreshRecent]);

  // Metadata Difference Highlighting (feature #3): recompute whenever the
  // selected file or its pending (unsaved) edits change, so highlighting
  // in the Inspection view stays live.
  const pendingCount = Object.keys(session.pending).length;
  useEffect(() => {
    if (!session.fileId) {
      setDiff(null);
      return;
    }
    let cancelled = false;
    api
      .getDiff(session.fileId)
      .then((d) => !cancelled && setDiff(d))
      .catch(() => !cancelled && setDiff(null));
    return () => {
      cancelled = true;
    };
  }, [session.fileId, pendingCount]);

  const diffMap = useMemo(() => {
    if (!diff) return undefined;
    const map: Record<string, "added" | "removed" | "modified"> = {};
    for (const e of diff.added) map[e.key] = "added";
    for (const e of diff.removed) map[e.key] = "removed";
    for (const e of diff.modified) map[e.key] = "modified";
    return map;
  }, [diff]);

  const handleUploaded = (res: UploadResponse) => {
    session.loadFromUpload(res.file_id, res.analysis);
    setSaveResult(null);
    setTab("inspect");
    refreshRecent();
  };

  const handleSelect = async (id: string) => {
    setSaveResult(null);
    setTab("inspect");
    await session.selectFile(id);
  };

  const handleRemove = async (id: string) => {
    await api.removeFile(id);
    if (session.fileId === id) session.clearSelection();
    refreshRecent();
  };

  // Shared between InsertMetadataPanel and MetadataEditor so staging a
  // field from either one lands in the same pending-edit state, and saving
  // from either one produces the same result banner.
  const handleApplyEdit = async (fieldKey: string, group: string, action: "set" | "remove", value?: unknown) => {
    await session.pushEdit({ field_key: fieldKey, group, action, new_value: value });
  };

  const handleSaved = (res: SaveAsResponse) => {
    setSaveResult(res);
    refreshRecent();
  };

  const hexField = session.analysis?.sections
    .flatMap((s) => s.fields)
    .find((f) => f.key === "bin:hex_preview");

  return (
    <div className="min-h-full">
      <Header status={status} />

      <main className="mx-auto flex max-w-7xl gap-6 px-6 py-6">
        <aside className="w-64 shrink-0">
          <div className="card sticky top-20 p-3">
            <h2 className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">
              Recent Files
            </h2>
            <RecentFilesList files={recentFiles} selectedId={session.fileId} onSelect={handleSelect} onRemove={handleRemove} />
          </div>
        </aside>

        <section className="min-w-0 flex-1">
          {!session.analysis ? (
            <div className="flex flex-col gap-6">
              <UploadZone onUploaded={handleUploaded} />
              <div className="card p-6 text-center text-sm text-[var(--color-grey-400)]">
                Select a recently analyzed file from the left, or drop a file above to begin.
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {session.loading && <p className="text-sm text-[var(--color-grey-400)]">Loading…</p>}
              {session.error && <p className="text-sm text-[var(--color-danger)]">{session.error}</p>}

              <UploadZone onUploaded={handleUploaded} />

              <div className="flex gap-1 border-b border-[var(--color-border)]">
                {([
                  ["inspect", "Inspection"],
                  ["editor", "Metadata Editor"],
                  ["tools", "Tools"],
                  ["cleanup", "Sanitization"],
                  ["history", "History"],
                ] as [Tab, string][]).map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setTab(key)}
                    className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
                      tab === key
                        ? "border-[var(--color-orange-500)] text-[var(--color-orange-700)]"
                        : "border-transparent text-[var(--color-grey-500)] hover:text-[var(--color-ink)]"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {saveResult && session.fileId && (
                <SaveResultBanner fileId={session.fileId} result={saveResult} onDismiss={() => setSaveResult(null)} />
              )}

              {tab === "inspect" && (
                <div className="flex flex-col gap-4">
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <FileIdentityCard analysis={session.analysis} />
                    <HashesCard hashes={session.analysis.hashes} />
                  </div>
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <MetadataSizeCard info={session.analysis.metadata_size} />
                    <MissingSuggestionsPanel suggestions={session.analysis.missing_suggestions} />
                  </div>
                  <DuplicatesPanel groups={session.analysis.duplicate_groups} />
                  <MetadataSections
                    analysis={session.analysis}
                    diffMap={diffMap}
                    onStageEdit={(f) => {
                      setStagedField(f);
                      setTab("editor");
                    }}
                  />
                  {hexField && <HexViewer hex={String(hexField.raw_value)} />}
                  {session.fileId && <ReportsPanel fileId={session.fileId} />}
                </div>
              )}

              {tab === "editor" && session.fileId && (
                <div className="flex flex-col gap-4">
                  {session.analysis && (
                    <InsertMetadataPanel
                      analysis={session.analysis}
                      fileId={session.fileId}
                      pending={session.pending}
                      onApplyEdit={handleApplyEdit}
                      onClearEdit={session.clearEdit}
                      onSaved={handleSaved}
                    />
                  )}
                  <MetadataEditor
                    fileId={session.fileId}
                    pending={session.pending}
                    stagedField={stagedField}
                    onClearStaged={() => setStagedField(null)}
                    onApplyEdit={handleApplyEdit}
                    onClearEdit={session.clearEdit}
                    onUndo={session.undo}
                    onRedo={session.redo}
                    onReset={session.resetPending}
                    onRevert={session.revertWorkingCopy}
                    onSaved={handleSaved}
                  />
                  <CustomTimestampsPanel fileId={session.fileId} />
                </div>
              )}

              {tab === "tools" && session.fileId && (
                <div className="flex flex-col gap-4">
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <SnapshotsPanel
                      fileId={session.fileId}
                      onRestored={(entries) => session.replacePending(entries)}
                    />
                    <DiffPanel fileId={session.fileId} refreshKey={pendingCount} />
                  </div>
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <CopyPasteMetadataPanel
                      fileId={session.fileId}
                      recentFiles={recentFiles}
                      onStaged={(entries) => session.mergeStagedFields(entries)}
                    />
                    <PresetsPanel
                      fileId={session.fileId}
                      onApplied={(entries) => session.mergeStagedFields(entries)}
                    />
                  </div>
                </div>
              )}

              {tab === "cleanup" && session.fileId && (
                <RemovalPresetsPanel fileId={session.fileId} onApplied={(a) => session.setAnalysis(a)} onSaved={handleSaved} />
              )}

              {tab === "history" && session.fileId && <HistoryPanel fileId={session.fileId} />}
            </div>
          )}
        </section>
      </main>

      <footer className="mx-auto max-w-7xl px-6 pb-8 pt-6">
        <div className="mx-auto h-px max-w-xs bg-gradient-to-r from-transparent via-[var(--color-border-strong)] to-transparent" />
        <p className="mt-4 text-center text-xs text-[var(--color-grey-400)]">
          The Umidasu runs entirely on your machine. Files are never sent to third-party services.
        </p>
        <p className="mt-1 text-center text-xs text-[var(--color-grey-300)]">
          Built by <span className="font-medium text-[var(--color-orange-600)]">TENETx0</span>
        </p>
      </footer>
    </div>
  );
}

export default App;
