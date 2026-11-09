import type {
  AnalysisResult,
  ApplyPresetResponse,
  CopyMetadataResponse,
  CustomTimestamps,
  MetadataDiff,
  MetadataPreset,
  MetadataSnapshot,
  OperationRecord,
  PendingEdit,
  PresetLogicalFields,
  RecentFile,
  SaveAsResponse,
  SystemStatus,
  UploadResponse,
} from "../types/metadata";

const BASE = "/api";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function handle<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail || detail;
    } catch {
      /* ignore non-JSON error body */
    }
    throw new ApiError(resp.status, detail);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  async systemStatus(): Promise<SystemStatus> {
    return handle(await fetch(`${BASE}/system/status`));
  },

  async uploadFile(file: File, onProgress?: (pct: number) => void): Promise<UploadResponse> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${BASE}/files/upload`);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          let detail = xhr.statusText;
          try {
            detail = JSON.parse(xhr.responseText).detail || detail;
          } catch {
            /* ignore */
          }
          reject(new ApiError(xhr.status, detail));
        }
      };
      xhr.onerror = () => reject(new ApiError(0, "Network error during upload"));
      const form = new FormData();
      form.append("file", file);
      xhr.send(form);
    });
  },

  async listRecentFiles(): Promise<RecentFile[]> {
    const data = await handle<{ files: RecentFile[] }>(await fetch(`${BASE}/files`));
    return data.files;
  },

  async getAnalysis(fileId: string): Promise<AnalysisResult> {
    return handle(await fetch(`${BASE}/files/${fileId}/analysis`));
  },

  async removeFile(fileId: string): Promise<void> {
    await handle(await fetch(`${BASE}/files/${fileId}`, { method: "DELETE" }));
  },

  async setPendingEdits(fileId: string, edits: PendingEdit[]): Promise<{ pending_count: number }> {
    return handle(
      await fetch(`${BASE}/files/${fileId}/edits`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ edits }),
      })
    );
  },

  async undoEdit(fileId: string): Promise<{ pending_count: number }> {
    return handle(await fetch(`${BASE}/files/${fileId}/edits/undo`, { method: "POST" }));
  },

  async redoEdit(fileId: string): Promise<{ pending_count: number }> {
    return handle(await fetch(`${BASE}/files/${fileId}/edits/redo`, { method: "POST" }));
  },

  async resetPendingEdits(fileId: string): Promise<void> {
    await handle(await fetch(`${BASE}/files/${fileId}/edits/reset`, { method: "POST" }));
  },

  async revertWorkingCopy(fileId: string): Promise<{ analysis: AnalysisResult }> {
    return handle(await fetch(`${BASE}/files/${fileId}/revert-working-copy`, { method: "POST" }));
  },

  async setCustomTimestamps(fileId: string, ts: CustomTimestamps): Promise<void> {
    await handle(
      await fetch(`${BASE}/files/${fileId}/custom-timestamps`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(ts),
      })
    );
  },

  async applyRemovalPreset(fileId: string, presets: string[]): Promise<{ result: unknown; analysis: AnalysisResult }> {
    return handle(
      await fetch(`${BASE}/files/${fileId}/remove-preset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ presets }),
      })
    );
  },

  async saveAs(fileId: string): Promise<SaveAsResponse> {
    return handle(await fetch(`${BASE}/files/${fileId}/save-as`, { method: "POST" }));
  },

  downloadUrl(fileId: string, outputName: string): string {
    return `${BASE}/files/${fileId}/download/${encodeURIComponent(outputName)}`;
  },

  async getHistory(fileId?: string): Promise<OperationRecord[]> {
    const url = fileId ? `${BASE}/history?file_id=${encodeURIComponent(fileId)}` : `${BASE}/history`;
    const data = await handle<{ operations: OperationRecord[] }>(await fetch(url));
    return data.operations;
  },

  async clearHistory(): Promise<void> {
    await handle(await fetch(`${BASE}/history/clear`, { method: "POST" }));
  },

  reportUrl(fileId: string, fmt: "json" | "csv" | "html"): string {
    return `${BASE}/files/${fileId}/report.${fmt}`;
  },

  // ----------------------------------------------------------- snapshots --
  async listSnapshots(fileId: string): Promise<MetadataSnapshot[]> {
    const data = await handle<{ snapshots: MetadataSnapshot[] }>(await fetch(`${BASE}/files/${fileId}/snapshots`));
    return data.snapshots;
  },

  async createSnapshot(fileId: string, label?: string): Promise<MetadataSnapshot> {
    const data = await handle<{ snapshot: MetadataSnapshot }>(
      await fetch(`${BASE}/files/${fileId}/snapshots`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label }),
      })
    );
    return data.snapshot;
  },

  async deleteSnapshot(fileId: string, snapshotId: string): Promise<void> {
    await handle(await fetch(`${BASE}/files/${fileId}/snapshots/${snapshotId}`, { method: "DELETE" }));
  },

  async restoreSnapshot(fileId: string, snapshotId: string): Promise<{ pending_count: number }> {
    return handle(await fetch(`${BASE}/files/${fileId}/snapshots/${snapshotId}/restore`, { method: "POST" }));
  },

  // ------------------------------------------------- difference highlighting
  async getDiff(fileId: string, snapshotId?: string): Promise<MetadataDiff> {
    const url = snapshotId
      ? `${BASE}/files/${fileId}/diff?snapshot_id=${encodeURIComponent(snapshotId)}`
      : `${BASE}/files/${fileId}/diff`;
    return handle(await fetch(url));
  },

  // ----------------------------------------------------------- copy & paste
  async copyMetadata(fileId: string, sourceFileId: string, fieldKeys?: string[]): Promise<CopyMetadataResponse> {
    return handle(
      await fetch(`${BASE}/files/${fileId}/copy-metadata`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_file_id: sourceFileId, field_keys: fieldKeys ?? null }),
      })
    );
  },

  // ----------------------------------------------------------------- presets
  async listPresets(): Promise<MetadataPreset[]> {
    const data = await handle<{ presets: MetadataPreset[] }>(await fetch(`${BASE}/presets`));
    return data.presets;
  },

  async createPreset(name: string, fields: PresetLogicalFields): Promise<MetadataPreset> {
    const data = await handle<{ preset: MetadataPreset }>(
      await fetch(`${BASE}/presets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, fields }),
      })
    );
    return data.preset;
  },

  async deletePreset(presetId: string): Promise<void> {
    await handle(await fetch(`${BASE}/presets/${presetId}`, { method: "DELETE" }));
  },

  async applyPreset(fileId: string, presetId: string): Promise<ApplyPresetResponse> {
    return handle(await fetch(`${BASE}/files/${fileId}/apply-preset/${presetId}`, { method: "POST" }));
  },
};

export { ApiError };
