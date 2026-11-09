import type { AnalysisResult } from "../types/metadata";

function Row({ label, value, warn }: { label: string; value: React.ReactNode; warn?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-[var(--color-border)] py-2 text-sm last:border-0">
      <span className="text-[var(--color-grey-500)]">{label}</span>
      <span className={`text-right font-medium ${warn ? "text-[var(--color-danger)]" : "text-[var(--color-ink)]"}`}>{value}</span>
    </div>
  );
}

export function FileIdentityCard({ analysis }: { analysis: AnalysisResult }) {
  const id = analysis.identity;
  return (
    <div className="card p-5">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">File Identity &amp; Integrity</h3>
      <Row label="Original filename" value={id.original_filename} />
      <Row label="Detected format" value={id.detected_format} />
      <Row label="MIME type" value={<span className="mono text-xs">{id.mime_type}</span>} />
      <Row label="Extension" value={`.${id.extension}`} />
      <Row label="Size" value={`${id.size_human} (${id.size_bytes.toLocaleString()} bytes)`} />
      <Row
        label="Extension matches content"
        value={id.extension_matches_format ? "Yes" : "No — MISMATCH"}
        warn={!id.extension_matches_format}
      />
      <Row label="Magic bytes" value={<span className="mono text-xs">{id.magic_bytes_hex}</span>} />
      <Row label="Entropy" value={`${analysis.entropy.toFixed(3)} bits/byte`} />
      <Row label="Filesystem modified" value={id.fs_modified ? new Date(id.fs_modified).toLocaleString() : "—"} />
      <Row label="Filesystem accessed" value={id.fs_accessed ? new Date(id.fs_accessed).toLocaleString() : "—"} />

      {!id.extension_matches_format && (
        <div className="mt-3 rounded-lg bg-[var(--color-danger-bg)] px-3 py-2 text-xs text-[var(--color-danger)]">
          <p>This file's content does not match its extension. It was analyzed by its real detected format, not its name.</p>
          {id.expected_extensions.length > 0 && (
            <p className="mt-1">
              Expected extension(s) for {id.detected_format}:{" "}
              <span className="mono font-semibold">{id.expected_extensions.map((e) => `.${e}`).join(", ")}</span> — actual:{" "}
              <span className="mono font-semibold">.{id.extension}</span>
            </p>
          )}
        </div>
      )}

      {analysis.appended_data && analysis.appended_data.checked && (
        <div
          className={`mt-3 rounded-lg px-3 py-2 text-xs ${
            analysis.appended_data.trailing_bytes ? "bg-[var(--color-danger-bg)] text-[var(--color-danger)]" : "bg-[var(--color-mist)] text-[var(--color-grey-500)]"
          }`}
        >
          <span className="font-medium">Appended-data check: </span>
          {analysis.appended_data.note}
        </div>
      )}
    </div>
  );
}
