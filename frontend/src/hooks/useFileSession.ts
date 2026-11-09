import { useCallback, useState } from "react";
import { api } from "../services/api";
import type { AnalysisResult, PendingEdit } from "../types/metadata";

export interface PendingEditState {
  [fieldKey: string]: { action: "set" | "remove"; value?: unknown; group: string };
}

export function useFileSession() {
  const [fileId, setFileId] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [pending, setPending] = useState<PendingEditState>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectFile = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const a = await api.getAnalysis(id);
      setFileId(id);
      setAnalysis(a);
      setPending({});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load file");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadFromUpload = useCallback((id: string, a: AnalysisResult) => {
    setFileId(id);
    setAnalysis(a);
    setPending({});
    setError(null);
  }, []);

  const pushEdit = useCallback(
    async (edit: PendingEdit) => {
      if (!fileId) return;
      const nextPending: PendingEditState = {
        ...pending,
        [edit.field_key]:
          edit.action === "remove"
            ? { action: "remove", group: edit.group }
            : { action: "set", value: edit.new_value, group: edit.group },
      };
      setPending(nextPending);
      const editsArray: PendingEdit[] = Object.entries(nextPending).map(([key, v]) => ({
        field_key: key,
        group: v.group,
        action: v.action,
        new_value: v.action === "set" ? v.value : undefined,
      }));
      await api.setPendingEdits(fileId, editsArray);
    },
    [fileId, pending]
  );

  const clearEdit = useCallback(
    async (fieldKey: string) => {
      if (!fileId) return;
      const nextPending = { ...pending };
      delete nextPending[fieldKey];
      setPending(nextPending);
      const editsArray: PendingEdit[] = Object.entries(nextPending).map(([key, v]) => ({
        field_key: key,
        group: v.group,
        action: v.action,
        new_value: v.action === "set" ? v.value : undefined,
      }));
      await api.setPendingEdits(fileId, editsArray);
    },
    [fileId, pending]
  );

  const undo = useCallback(async () => {
    if (!fileId) return;
    await api.undoEdit(fileId);
    const a = await api.getAnalysis(fileId);
    setAnalysis(a);
  }, [fileId]);

  const redo = useCallback(async () => {
    if (!fileId) return;
    await api.redoEdit(fileId);
    const a = await api.getAnalysis(fileId);
    setAnalysis(a);
  }, [fileId]);

  const resetPending = useCallback(async () => {
    if (!fileId) return;
    await api.resetPendingEdits(fileId);
    setPending({});
  }, [fileId]);

  const revertWorkingCopy = useCallback(async () => {
    if (!fileId) return;
    const res = await api.revertWorkingCopy(fileId);
    setAnalysis(res.analysis);
    setPending({});
  }, [fileId]);

  const refreshAnalysis = useCallback(async () => {
    if (!fileId) return;
    const a = await api.getAnalysis(fileId);
    setAnalysis(a);
  }, [fileId]);

  /** Mirror fields the server already staged into sess.pending_values via
   * a dedicated endpoint (Copy & Paste, Presets) into the local pending
   * state, without re-issuing a redundant PUT /edits call. */
  const mergeStagedFields = useCallback((entries: { key: string; value: unknown; group?: string }[]) => {
    setPending((prev) => {
      const next = { ...prev };
      for (const e of entries) {
        next[e.key] = { action: "set", value: e.value, group: e.group ?? "" };
      }
      return next;
    });
  }, []);

  /** Replace the local pending mirror wholesale — used after a Snapshot
   * Restore, which replaces sess.pending_values server-side rather than
   * merging into it. */
  const replacePending = useCallback(
    (entries: { key: string; action: "set" | "remove"; value?: unknown; group?: string }[]) => {
      const next: PendingEditState = {};
      for (const e of entries) {
        next[e.key] = e.action === "remove" ? { action: "remove", group: e.group ?? "" } : { action: "set", value: e.value, group: e.group ?? "" };
      }
      setPending(next);
    },
    []
  );

  const clearSelection = useCallback(() => {
    setFileId(null);
    setAnalysis(null);
    setPending({});
  }, []);

  return {
    fileId,
    analysis,
    pending,
    loading,
    error,
    selectFile,
    loadFromUpload,
    pushEdit,
    clearEdit,
    undo,
    redo,
    resetPending,
    revertWorkingCopy,
    refreshAnalysis,
    clearSelection,
    setAnalysis,
    mergeStagedFields,
    replacePending,
  };
}
