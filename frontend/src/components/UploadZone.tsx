import { useCallback, useRef, useState } from "react";
import { api, ApiError } from "../services/api";
import type { UploadResponse } from "../types/metadata";

export function UploadZone({ onUploaded }: { onUploaded: (res: UploadResponse) => void }) {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const doUpload = useCallback(
    async (file: File) => {
      setUploading(true);
      setProgress(0);
      setError(null);
      try {
        const res = await api.uploadFile(file, setProgress);
        onUploaded(res);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Upload failed");
      } finally {
        setUploading(false);
      }
    },
    [onUploaded]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file) doUpload(file);
    },
    [doUpload]
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      className={`card flex flex-col items-center justify-center gap-3 border-2 border-dashed px-8 py-14 text-center transition-colors ${
        dragOver ? "border-[var(--color-orange-400)] bg-[var(--color-orange-50)]" : "border-[var(--color-border-strong)]"
      }`}
    >
      <div className="rounded-full bg-[var(--color-orange-50)] p-4">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#baff29" strokeWidth="2">
          <path d="M12 16V4M12 4l-4 4M12 4l4 4" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <div>
        <p className="font-medium text-[var(--color-ink)]">Drag &amp; drop a file to inspect</p>
        <p className="text-sm text-[var(--color-grey-500)]">Images, video, audio, PDFs, Office docs, archives, and more</p>
      </div>
      <button
        type="button"
        className="btn-primary rounded-lg px-4 py-2 text-sm font-medium"
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
      >
        {uploading ? `Uploading… ${progress}%` : "Browse Files"}
      </button>
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) doUpload(file);
          e.target.value = "";
        }}
      />
      {uploading && (
        <div className="h-1.5 w-64 overflow-hidden rounded-full bg-[var(--color-mist)]">
          <div className="h-full bg-[var(--color-orange-500)] transition-all" style={{ width: `${progress}%` }} />
        </div>
      )}
      {error && <p className="text-sm text-[var(--color-danger)]">{error}</p>}
      <p className="text-xs text-[var(--color-grey-400)]">Files stay local — nothing is sent to third-party services.</p>
    </div>
  );
}
