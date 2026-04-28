"use client";

import { useState } from "react";
import { SeverityBadge } from "@/components/SeverityBadge";
import type { QuestionFlags } from "@/lib/api";

export function QuestionFlag({ q }: { q: QuestionFlags }) {
  const [expanded, setExpanded] = useState(q.severity === "high");
  const hasDetails = q.paraphrase_shift !== null || q.irt !== null;

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] overflow-hidden">
      <button
        onClick={() => hasDetails && setExpanded((v) => !v)}
        disabled={!hasDetails}
        className="w-full p-4 text-left flex items-start justify-between gap-3 hover:bg-white/3 disabled:cursor-default disabled:hover:bg-transparent"
      >
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-[var(--color-text-muted)]">
              {q.question_id}
            </span>
            <SeverityBadge severity={q.severity} />
            <span className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
              {q.type.replace("_", " ")}
            </span>
          </div>
          <p className="mt-1.5 text-sm">{q.question_text}</p>
        </div>
        {hasDetails && (
          <span className="text-xs text-[var(--color-text-muted)] shrink-0 mt-1">
            {expanded ? "−" : "+"}
          </span>
        )}
      </button>

      {expanded && (
        <div className="border-t border-[var(--color-border)] p-4 space-y-4 bg-black/20">
          {(q.paraphrase_shift?.summary || q.irt?.summary) && (
            <div className="rounded-md border border-[var(--color-accent)]/30 bg-[var(--color-accent)]/5 p-3 space-y-1.5">
              {q.paraphrase_shift?.summary && (
                <div className="text-sm leading-snug">
                  <span className="font-semibold text-[var(--color-accent)]">
                    Wording:{" "}
                  </span>
                  {q.paraphrase_shift.summary}
                </div>
              )}
              {q.irt?.summary && (
                <div className="text-sm leading-snug">
                  <span className="font-semibold text-[var(--color-accent)]">
                    Discrimination:{" "}
                  </span>
                  {q.irt.summary}
                </div>
              )}
            </div>
          )}
          {q.paraphrase_shift && q.paraphrase_shift.metric !== "skipped" && (
            <ParaphraseShiftDetail flag={q.paraphrase_shift} />
          )}
          {q.paraphrase_shift?.note && (
            <div className="text-xs text-[var(--color-text-muted)]">
              note: {q.paraphrase_shift.note}
            </div>
          )}
          {q.irt && <IRTDetail flag={q.irt} />}
        </div>
      )}
    </div>
  );
}

function ParaphraseShiftDetail({
  flag,
}: {
  flag: NonNullable<QuestionFlags["paraphrase_shift"]>;
}) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <h4 className="text-xs uppercase tracking-wider text-[var(--color-text-muted)]">
          Counterfactual paraphrase shift
        </h4>
        <SeverityBadge severity={flag.severity} />
      </div>
      <div className="mt-2 grid grid-cols-3 gap-3 text-xs">
        <Stat label={flag.metric} value={flag.score.toFixed(3)} />
        <Stat
          label="cohen's d"
          value={flag.cohens_d === null ? "n/a" : flag.cohens_d.toFixed(2)}
        />
        <Stat label="n personas" value={flag.n_personas.toString()} />
      </div>
      {flag.examples.length > 0 && (
        <div className="mt-3 space-y-1.5">
          <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
            Wording variants × mean response
          </div>
          {flag.examples.map((ex) => (
            <div
              key={ex.paraphrase_idx}
              className="rounded border border-[var(--color-border)] bg-black/20 p-2 text-xs"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="line-clamp-2">{ex.text}</span>
                <span className="font-mono text-[var(--color-text-muted)] shrink-0">
                  μ={ex.mean_response.toFixed(2)} (n={ex.n})
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function IRTDetail({ flag }: { flag: NonNullable<QuestionFlags["irt"]> }) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <h4 className="text-xs uppercase tracking-wider text-[var(--color-text-muted)]">
          IRT 2PL discrimination
          <span className="ml-2 text-[10px] normal-case text-[var(--color-text-muted)]">
            (relative-within-survey, not absolute)
          </span>
        </h4>
        <SeverityBadge severity={flag.severity} />
      </div>
      <div className="mt-2 grid grid-cols-3 gap-3 text-xs">
        <Stat label="discrimination a" value={flag.discrimination.toFixed(2)} />
        <Stat label="interpretation" value={flag.interpretation} />
        <Stat
          label="convergence"
          value={flag.convergence_ok ? "ok" : "fallback"}
        />
      </div>
      {flag.note && (
        <div className="mt-2 text-xs text-[var(--color-text-muted)]">
          note: {flag.note}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
        {label}
      </div>
      <div className="font-mono text-sm">{value}</div>
    </div>
  );
}
