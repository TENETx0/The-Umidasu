import { api } from "../services/api";

export function ReportsPanel({ fileId }: { fileId: string }) {
  return (
    <div className="card p-5">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">Export Inspection Report</h3>
      <div className="flex flex-wrap gap-2">
        {(["json", "csv", "html"] as const).map((fmt) => (
          <a
            key={fmt}
            href={api.reportUrl(fileId, fmt)}
            download={`umidasu-report.${fmt}`}
            className="btn-secondary rounded-lg px-3 py-1.5 text-sm font-medium uppercase"
          >
            {fmt}
          </a>
        ))}
      </div>
    </div>
  );
}
