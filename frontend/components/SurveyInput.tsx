"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export function SurveyInput() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [quickMode, setQuickMode] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch {
      setError("Input is not valid JSON");
      return;
    }
    setSubmitting(true);
    try {
      const { run_id } = await api.createRun(parsed, quickMode);
      router.push(`/run/${run_id}`);
    } catch (e) {
      setError((e as Error).message);
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-5">
      <label className="text-sm font-medium">Custom survey JSON</label>
      <p className="mt-1 text-xs text-[var(--color-text-muted)]">
        Paste a Knit-shaped survey JSON. Schema docs: brief + audience +
        questions + screener + quotas + fielding.
      </p>
      <textarea
        spellCheck={false}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder='{ "id": "my-survey", "version": "0.1", ... }'
        className="mt-3 w-full h-48 rounded-md border border-[var(--color-border)] bg-black/40 p-3 font-mono text-xs focus:outline-none focus:border-[var(--color-accent)]/60"
      />
      <div className="mt-3 flex items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
          <input
            type="checkbox"
            checked={quickMode}
            onChange={(e) => setQuickMode(e.target.checked)}
            className="accent-[var(--color-accent)]"
          />
          Quick mode (500 personas; ~3 min, ~$12)
        </label>
        <button
          onClick={submit}
          disabled={submitting || text.trim() === ""}
          className="rounded-md border border-[var(--color-accent)]/60 bg-[var(--color-accent)]/10 px-4 py-2 text-sm font-medium text-[var(--color-accent)] hover:bg-[var(--color-accent)]/20 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? "submitting…" : "Run Pre-Flight"}
        </button>
      </div>
      {error && (
        <div className="mt-3 rounded border border-red-500/40 bg-red-500/5 p-3 text-xs text-red-200">
          {error}
        </div>
      )}
    </div>
  );
}
