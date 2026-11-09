import type { RecentFile } from "../types/metadata";

export function RecentFilesList({
  files,
  selectedId,
  onSelect,
  onRemove,
}: {
  files: RecentFile[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onRemove: (id: string) => void;
}) {
  if (files.length === 0) {
    return <p className="px-3 py-6 text-center text-sm text-[var(--color-grey-400)]">No files analyzed yet this session.</p>;
  }
  return (
    <ul className="flex flex-col gap-1">
      {files.map((f) => (
        <li key={f.file_id}>
          <div
            data-active={selectedId === f.file_id}
            className={`recent-row group flex cursor-pointer items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
              selectedId === f.file_id ? "bg-[var(--color-orange-50)] text-[var(--color-orange-700)]" : "hover:bg-[var(--color-mist)]"
            }`}
            onClick={() => onSelect(f.file_id)}
          >
            <div className="min-w-0">
              <p className="truncate font-medium">{f.original_filename}</p>
              <p className="truncate text-xs text-[var(--color-grey-400)]">{f.detected_format}</p>
            </div>
            <button
              type="button"
              title="Remove file"
              className="shrink-0 rounded p-1 text-[var(--color-grey-400)] opacity-0 hover:bg-[var(--color-mist)] hover:text-[var(--color-danger)] group-hover:opacity-100"
              onClick={(e) => {
                e.stopPropagation();
                onRemove(f.file_id);
              }}
            >
              ✕
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
