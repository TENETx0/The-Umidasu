import type { SystemStatus } from "../types/metadata";

export function Header({ status }: { status: SystemStatus | null }) {
  return (
    <header className="sticky top-0 z-20 border-b border-[var(--color-border)] bg-black/85 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
        <div className="flex items-center gap-3">
          <svg width="30" height="30" viewBox="0 0 32 32" className="logo-mark shrink-0">
            <rect width="32" height="32" rx="7" fill="#0d0d0d" stroke="#2a2a2a" />
            <circle cx="13.5" cy="13.5" r="7" fill="none" stroke="#baff29" strokeWidth="2.6" />
            <line x1="18.6" y1="18.6" x2="25" y2="25" stroke="#baff29" strokeWidth="2.8" strokeLinecap="round" />
          </svg>
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-[var(--color-ink)]">The Umidasu</h1>
            <p className="text-xs text-[var(--color-grey-500)]">Universal Metadata Inspector, Editor &amp; File Analyzer</p>
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs">
          {status && (
            <div className="flex items-center gap-2">
              {status.tools.map((t) => (
                <span
                  key={t.name}
                  title={t.available ? t.version ?? "available" : "not installed"}
                  className={`badge ${
                    t.available ? "bg-[var(--color-orange-50)] text-[var(--color-orange-700)]" : "bg-[var(--color-grey-100)] text-[var(--color-grey-400)]"
                  }`}
                >
                  {t.name}
                </span>
              ))}
            </div>
          )}
          <span className="h-3 w-px bg-[var(--color-border)]" aria-hidden="true" />
          <span className="text-[var(--color-grey-400)]">v{status?.app_version ?? "1.0.0"}</span>
          <span className="text-[var(--color-grey-300)]">
            by <span className="font-medium text-[var(--color-grey-500)]">{status?.app_author ?? "TENETx0"}</span>
          </span>
        </div>
      </div>
    </header>
  );
}
