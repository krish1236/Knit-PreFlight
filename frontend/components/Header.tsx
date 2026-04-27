export function Header() {
  return (
    <header className="border-b border-[var(--color-border)] bg-[var(--color-bg-elevated)]">
      <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl font-semibold tracking-tight">Pre-Flight</span>
          <span className="text-xs text-[var(--color-text-muted)] hidden sm:inline">
            pre-launch quality gate for AI-generated research surveys
          </span>
        </div>
        <nav className="flex items-center gap-4 text-sm text-[var(--color-text-muted)]">
          <a href="/" className="hover:text-[var(--color-text)]">
            Run a survey
          </a>
          <a href="/calibration" className="hover:text-[var(--color-text)]">
            Calibration
          </a>
        </nav>
      </div>
    </header>
  );
}
