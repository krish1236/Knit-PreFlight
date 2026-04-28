"use client";

import { useEffect, useState } from "react";
import { Header } from "@/components/Header";

interface CalibrationData {
  status: "ok" | "calibration_pending";
  f1_overall: number | null;
  f1_per_class: Record<string, number | Record<string, number>>;
  n_surveys: number;
  benchmark: string;
  last_run: { git_sha: string; completed_at: string } | null;
  history: Array<{ git_sha: string; f1_overall: number; completed_at: string }>;
}

export default function CalibrationPage() {
  const [data, setData] = useState<CalibrationData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/calibration")
      .then((r) => r.json())
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-6xl px-6 py-10 space-y-8">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Calibration dashboard
          </h1>
          <p className="mt-2 text-[var(--color-text-muted)] text-sm max-w-2xl">
            F1 score on a held-out defect-injection benchmark — clean Pew /
            ANES / GSS instruments injected with bias-catalog defects across
            three severity levels (subtle / moderate / obvious). The headline
            number always sits next to the per-severity breakdown so it can
            never be cherry-picked.
          </p>
        </div>

        {error && (
          <div className="rounded-lg border border-red-500/40 bg-red-500/5 p-4 text-sm text-red-200">
            {error}
          </div>
        )}

        {!data && !error && (
          <div className="h-32 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] animate-pulse" />
        )}

        {data && data.status === "calibration_pending" && (
          <div className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-6">
            <div className="text-sm font-medium text-amber-200">
              Calibration pending
            </div>
            <p className="mt-2 text-sm text-[var(--color-text-muted)]">
              {data.benchmark}
            </p>
          </div>
        )}

        {data && data.status === "ok" && (
          <>
            <section className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-6">
              <div className="flex items-baseline gap-4">
                <span className="text-5xl font-mono font-semibold text-[var(--color-accent)]">
                  {data.f1_overall?.toFixed(3)}
                </span>
                <span className="text-sm text-[var(--color-text-muted)]">
                  aggregate F1 across {data.n_surveys} surveys
                </span>
              </div>
              {data.last_run && (
                <p className="mt-3 text-xs text-[var(--color-text-muted)] font-mono">
                  {data.last_run.git_sha.slice(0, 8)} · {data.last_run.completed_at}
                </p>
              )}
            </section>

            <section>
              <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                Per-defect-class F1
              </h2>
              <div className="mt-3 space-y-2">
                {Object.entries(data.f1_per_class).map(([cls, value]) => (
                  <div
                    key={cls}
                    className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-3 flex items-center justify-between"
                  >
                    <span className="font-mono text-sm">{cls}</span>
                    <span className="font-mono text-sm">
                      {typeof value === "number"
                        ? value.toFixed(3)
                        : JSON.stringify(value)}
                    </span>
                  </div>
                ))}
              </div>
            </section>

            {data.history.length > 1 && (
              <section>
                <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                  Recent calibration runs
                </h2>
                <div className="mt-3 space-y-1">
                  {data.history.map((h) => (
                    <div
                      key={h.git_sha + h.completed_at}
                      className="flex items-center justify-between rounded border border-[var(--color-border)] px-3 py-2 text-xs font-mono"
                    >
                      <span>{h.git_sha.slice(0, 8)}</span>
                      <span>{h.f1_overall.toFixed(3)}</span>
                      <span className="text-[var(--color-text-muted)]">
                        {h.completed_at.split("T")[0]}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
