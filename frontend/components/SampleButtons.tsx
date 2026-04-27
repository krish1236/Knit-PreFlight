"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type SampleListing } from "@/lib/api";

export function SampleButtons() {
  const router = useRouter();
  const [samples, setSamples] = useState<SampleListing[] | null>(null);
  const [loadingSlug, setLoadingSlug] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listSamples()
      .then(setSamples)
      .catch((e: Error) => setError(e.message));
  }, []);

  async function runSample(slug: string) {
    setLoadingSlug(slug);
    setError(null);
    try {
      const { run_id } = await api.runSample(slug);
      router.push(`/run/${run_id}`);
    } catch (e) {
      setError((e as Error).message);
      setLoadingSlug(null);
    }
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/40 bg-red-500/5 p-4 text-sm text-red-200">
        Failed to load samples: {error}
      </div>
    );
  }

  if (samples === null) {
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-24 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] animate-pulse"
          />
        ))}
      </div>
    );
  }

  if (samples.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-6 text-sm text-[var(--color-text-muted)]">
        No sample surveys available. Run{" "}
        <code className="rounded bg-black/40 px-1.5 py-0.5">
          python -m preflight.cli seed-samples
        </code>{" "}
        and reload.
      </div>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-1">
      {samples.map((s) => (
        <button
          key={s.slug}
          onClick={() => runSample(s.slug)}
          disabled={loadingSlug !== null}
          className="text-left rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-5 hover:border-[var(--color-accent)]/60 transition-colors disabled:opacity-60 disabled:cursor-wait"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="font-medium">
                {humanLabel(s.slug)}
              </div>
              <div className="text-sm text-[var(--color-text-muted)] mt-1">
                {s.title}
              </div>
              <div className="text-xs text-[var(--color-text-muted)] mt-2">
                Audience: {s.objective}
              </div>
            </div>
            <div className="text-xs text-[var(--color-text-muted)] shrink-0">
              {s.cached_run_status === "completed" ? (
                <span className="text-[var(--color-accent)]">cached</span>
              ) : loadingSlug === s.slug ? (
                <span>starting…</span>
              ) : (
                <span>run sample</span>
              )}
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}

function humanLabel(slug: string): string {
  return slug
    .replace(/^\d+_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
