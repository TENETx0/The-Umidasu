import { useMemo, useState } from "react";

function toAscii(byte: number): string {
  return byte >= 32 && byte < 127 ? String.fromCharCode(byte) : ".";
}

export function HexViewer({ hex }: { hex: string }) {
  const [visibleRows, setVisibleRows] = useState(16);
  const bytes = useMemo(() => {
    const arr: number[] = [];
    for (let i = 0; i < hex.length; i += 2) {
      arr.push(parseInt(hex.slice(i, i + 2), 16));
    }
    return arr;
  }, [hex]);

  const rows = useMemo(() => {
    const perRow = 16;
    const out: { offset: number; bytes: number[] }[] = [];
    for (let i = 0; i < bytes.length && out.length < visibleRows; i += perRow) {
      out.push({ offset: i, bytes: bytes.slice(i, i + perRow) });
    }
    return out;
  }, [bytes, visibleRows]);

  return (
    <div className="card p-5">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">Hex Viewer</h3>
      <div className="mono overflow-x-auto rounded-lg bg-[var(--color-mist)] p-3 text-xs leading-6">
        {rows.map((row) => (
          <div key={row.offset} className="flex gap-4 whitespace-pre">
            <span className="text-[var(--color-grey-400)]">{row.offset.toString(16).padStart(8, "0")}</span>
            <span className="text-[var(--color-ink-soft)]">
              {row.bytes.map((b) => b.toString(16).padStart(2, "0")).join(" ").padEnd(47, " ")}
            </span>
            <span className="text-[var(--color-orange-700)]">{row.bytes.map(toAscii).join("")}</span>
          </div>
        ))}
      </div>
      {visibleRows < bytes.length / 16 && (
        <button
          type="button"
          className="btn-secondary mt-2 rounded px-3 py-1 text-xs"
          onClick={() => setVisibleRows((v) => v + 32)}
        >
          Show more
        </button>
      )}
    </div>
  );
}
