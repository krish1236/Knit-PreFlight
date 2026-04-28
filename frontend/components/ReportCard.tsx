import { QuestionFlag } from "@/components/QuestionFlag";
import { SeverityBadge } from "@/components/SeverityBadge";
import type { ReportCard as ReportCardData } from "@/lib/api";

export function ReportCard({ report }: { report: ReportCardData }) {
  const exposure = report.estimated_panel_exposure;

  return (
    <div className="space-y-8">
      <section className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-5">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
            Summary
          </h2>
          <span className="text-xs text-[var(--color-text-muted)]">
            survey {report.survey_id}
          </span>
        </div>
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-4">
          <SummaryStat
            label="High-severity questions"
            value={exposure.high_severity_questions}
            tone="red"
          />
          <SummaryStat
            label="Medium-severity questions"
            value={exposure.medium_severity_questions}
            tone="amber"
          />
          <SummaryStat
            label="Redundant pairs"
            value={report.redundancy_pairs.length}
            tone={report.redundancy_pairs.length > 0 ? "amber" : "neutral"}
          />
          <SummaryStat
            label="Screener / quota issues"
            value={
              report.screener_issues.length +
              report.quota_feasibility.filter((q) => q.severity !== "none")
                .length
            }
            tone={
              report.screener_issues.some((s) => s.severity === "high")
                ? "red"
                : "neutral"
            }
          />
        </div>
        <div className="mt-4 rounded border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-100">
          {report.framing_disclaimer}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
          Per-question signals
        </h2>
        <div className="mt-4 space-y-3">
          {report.per_question.map((q) => (
            <QuestionFlag key={q.question_id} q={q} />
          ))}
        </div>
      </section>

      {report.redundancy_pairs.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
            Redundant pairs
          </h2>
          <div className="mt-3 space-y-2">
            {report.redundancy_pairs.map((r) => (
              <div
                key={`${r.q_id_a}-${r.q_id_b}`}
                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4 space-y-2"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-mono text-xs">
                      {r.q_id_a} ↔ {r.q_id_b}
                    </div>
                    {r.summary && (
                      <div className="text-sm mt-1">{r.summary}</div>
                    )}
                  </div>
                  <SeverityBadge severity={r.severity} />
                </div>
                <div className="text-xs text-[var(--color-text-muted)] font-mono">
                  Pearson {r.pearson.toFixed(2)} · Spearman{" "}
                  {r.spearman.toFixed(2)} · n={r.n_personas}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {report.screener_issues.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
            Screener / skip-logic issues
          </h2>
          <div className="mt-3 space-y-2">
            {report.screener_issues.map((s, i) => (
              <div
                key={i}
                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4 space-y-2"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-mono text-xs uppercase">{s.type}</div>
                    {s.summary ? (
                      <div className="text-sm mt-1">{s.summary}</div>
                    ) : (
                      <div className="text-sm mt-1">{s.description}</div>
                    )}
                  </div>
                  <SeverityBadge severity={s.severity} />
                </div>
                {s.summary && (
                  <div className="text-xs text-[var(--color-text-muted)]">
                    detail: {s.description}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {report.quota_feasibility.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
            Quota feasibility
          </h2>
          <div className="mt-3 space-y-2">
            {report.quota_feasibility.map((q, i) => (
              <div
                key={i}
                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4 space-y-2"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-mono text-xs">
                      {JSON.stringify(q.cell)}
                    </div>
                    {q.summary && (
                      <div className="text-sm mt-1">{q.summary}</div>
                    )}
                  </div>
                  <SeverityBadge severity={q.severity} />
                </div>
                <div className="text-xs text-[var(--color-text-muted)] font-mono">
                  panel pct: {q.estimated_panel_pct.toFixed(2)}% · projected n:{" "}
                  {q.estimated_n_at_target} of target {q.target_n}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function SummaryStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "red" | "amber" | "neutral";
}) {
  const toneStyle =
    tone === "red"
      ? "text-red-300"
      : tone === "amber"
        ? "text-amber-300"
        : "text-[var(--color-text)]";
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
        {label}
      </div>
      <div className={`font-mono text-2xl mt-1 ${toneStyle}`}>{value}</div>
    </div>
  );
}
