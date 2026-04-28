"use client";

import { useEffect, useState } from "react";
import { api, type RunStateView } from "@/lib/api";

const PHASES: Array<{ status: string; label: string }> = [
  { status: "pending", label: "Queued" },
  { status: "personas_ready", label: "Persona pool generated" },
  { status: "paraphrases_ready", label: "Paraphrases generated" },
  { status: "probing", label: "Collecting probe responses" },
  { status: "stats_running", label: "Running statistical analyzers" },
  { status: "completed", label: "Report ready" },
];

export function RunProgress({
  runId,
  onCompleted,
}: {
  runId: string;
  onCompleted: () => void;
}) {
  const [run, setRun] = useState<RunStateView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    api
      .getRun(runId)
      .then((r) => {
        if (mounted) {
          setRun(r);
          if (r.status === "completed") onCompleted();
        }
      })
      .catch((e: Error) => mounted && setError(e.message));

    const url = `/api/runs/${runId}/stream`;
    const source = new EventSource(url);

    source.addEventListener("status", (event) => {
      if (!mounted) return;
      try {
        const data = JSON.parse((event as MessageEvent).data);
        setRun((prev) =>
          prev
            ? { ...prev, status: data.status, completed_at: data.completed_at }
            : prev,
        );
        if (data.status === "completed") {
          onCompleted();
          source.close();
        }
        if (data.status === "failed") {
          setError("Run failed. Check worker logs.");
          source.close();
        }
      } catch {}
    });

    source.addEventListener("error", () => {
      if (!mounted) return;
    });

    return () => {
      mounted = false;
      source.close();
    };
  }, [runId, onCompleted]);

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/40 bg-red-500/5 p-5 text-sm text-red-200">
        {error}
      </div>
    );
  }

  const currentIdx = PHASES.findIndex((p) => p.status === run?.status);

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
        Pipeline progress
      </h2>
      <ol className="mt-4 space-y-2">
        {PHASES.map((phase, idx) => {
          const isActive = idx === currentIdx;
          const isDone =
            currentIdx === -1
              ? false
              : idx < currentIdx ||
                (phase.status === "completed" && currentIdx === idx);
          return (
            <li
              key={phase.status}
              className={`flex items-center gap-3 text-sm ${
                isActive
                  ? "text-[var(--color-accent)]"
                  : isDone
                    ? "text-[var(--color-text)]"
                    : "text-[var(--color-text-muted)]"
              }`}
            >
              <span
                className={`inline-block h-2 w-2 rounded-full ${
                  isActive
                    ? "bg-[var(--color-accent)] animate-pulse"
                    : isDone
                      ? "bg-[var(--color-accent)]"
                      : "bg-[var(--color-border)]"
                }`}
              />
              {phase.label}
            </li>
          );
        })}
      </ol>
      <p className="mt-4 text-xs text-[var(--color-text-muted)]">
        Custom runs typically take 3–8 minutes (Quick mode: ~3 min). Sample
        runs return cached reports instantly after the first fielding.
      </p>
    </div>
  );
}
