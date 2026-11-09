import { useState } from "react";
import type { FileHashes } from "../types/metadata";

function HashRow({ label, value, note }: { label: string; value: string; note: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="border-b border-[var(--color-border)] py-2 last:border-0">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-[var(--color-ink)]">{label}</span>
        <button
          type="button"
          className="text-xs text-[var(--color-orange-600)] hover:underline"
          onClick={() => {
            navigator.clipboard.writeText(value);
            setCopied(true);
            setTimeout(() => setCopied(false), 1200);
          }}
        >
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
      <p className="mono mt-0.5 break-all text-xs text-[var(--color-grey-500)]">{value}</p>
      <p className="mt-0.5 text-[11px] italic text-[var(--color-grey-400)]">{note}</p>
    </div>
  );
}

export function HashesCard({ hashes }: { hashes: FileHashes }) {
  return (
    <div className="card p-5">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">Cryptographic Hashes</h3>
      <HashRow label="SHA-256" value={hashes.sha256} note={hashes.security_notes.sha256} />
      <HashRow label="SHA-512" value={hashes.sha512} note={hashes.security_notes.sha512} />
      <HashRow label="SHA-1" value={hashes.sha1} note={hashes.security_notes.sha1} />
      <HashRow label="MD5" value={hashes.md5} note={hashes.security_notes.md5} />
    </div>
  );
}
