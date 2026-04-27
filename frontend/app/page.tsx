import { Header } from "@/components/Header";
import { SampleButtons } from "@/components/SampleButtons";
import { SurveyInput } from "@/components/SurveyInput";

export default function Home() {
  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-6xl px-6 py-12">
        <section className="max-w-3xl">
          <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight">
            Catch survey-side defects before fielding.
          </h1>
          <p className="mt-4 text-[var(--color-text-muted)] leading-relaxed">
            Pre-Flight runs a calibrated swarm of persona-conditioned LLM
            probes against a draft survey to detect leading questions,
            infeasible screeners, redundant pairs, and low-discriminative
            wording. Probes are used for instrument stress-testing, not
            population response prediction. Calibration is via defect
            injection against a held-out corpus.
          </p>
        </section>

        <div className="mt-10 grid gap-8 lg:grid-cols-2">
          <section>
            <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
              Run a sample
            </h2>
            <p className="mt-2 mb-4 text-xs text-[var(--color-text-muted)]">
              Three pre-built surveys covering clean baseline,
              defect-bearing, and mixed-quality cases.
            </p>
            <SampleButtons />
          </section>

          <section>
            <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
              Or upload your own
            </h2>
            <p className="mt-2 mb-4 text-xs text-[var(--color-text-muted)]">
              Paste a Knit-shaped survey JSON. Live runs take 3–8 min.
            </p>
            <SurveyInput />
          </section>
        </div>
      </main>
    </div>
  );
}
