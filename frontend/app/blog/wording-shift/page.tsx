import type { Metadata } from "next";
import { Header } from "@/components/Header";

export const metadata: Metadata = {
  title: "Catching wording bias before fielding · Pre-Flight",
  description:
    "How counterfactual paraphrase probing turns a leading question into a number you can act on, what makes the signal trustworthy, and what we deliberately did not try to detect.",
};

export default function WordingShiftPost() {
  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-2xl px-6 py-16">
        <article className="prose-preflight">
          <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight leading-tight">
            Catching wording bias before fielding
          </h1>
          <p className="mt-3 text-sm text-[var(--color-text-muted)]">
            April 28, 2026 · 6 minute read
          </p>

          <Section>
            <p>
              A market research team writes a tracker question. It reads,
              Wouldn&apos;t you agree that Pacific Pure offers good value
              compared to similar brands. The wording feels conversational and
              nobody flags it on review. The survey ships to eight hundred
              panelists. The topline says seventy three percent of consumers
              believe the brand offers good value, marketing builds a launch
              narrative around it, and the client is happy.
            </p>
            <p>
              None of that number is doing what the team thinks it is doing.
              The wording did the work. If the same question had been written
              as, How does Pacific Pure compare to similar brands on value, the
              agreement number would have landed somewhere around three on a
              five point scale. The eight hundred panelists are not lying. They
              are answering a question that loads its own answer.
            </p>
            <p>
              Pre-Flight catches this kind of thing before the survey leaves
              the platform. This post is about how the detection actually
              works, what makes the signal trustworthy without claiming
              anything we cannot back up, and what we deliberately did not try
              to detect in the first cut.
            </p>
          </Section>

          <H2>What the report card actually shows</H2>
          <Section>
            <p>
              On the defect bearing sample, the report card flags Q4 as high
              severity and prints a sentence right above the metrics. It says,
              Original wording inflates mean response by about one point three
              four points (original mean four point three two versus neutral
              paraphrases mean two point nine eight). This question is leading
              and will skew your data. Below that sentence sits a small table
              of the original question and five rephrased variants with the
              mean response next to each one.
            </p>
            <p>
              The numbers are the entire story. The original wording pulls one
              hundred and fifty matched personas to a mean of four point three
              two, which on a five point scale is roughly mid agree. Five
              neutral paraphrases of the same question pull the same one
              hundred and fifty personas to a mean of two point nine eight,
              which is roughly neutral. A one point three four point swing on a
              five point scale is the wording adding about thirty percent to
              the agreement number, untouched by anyone&apos;s real opinion.
            </p>
          </Section>

          <H2>How we get there</H2>
          <Section>
            <p>
              Generate five paraphrases per question with Haiku. The system
              prompt forces each paraphrase to vary on a different axis, so we
              do not end up with five mild rewrites of the same sentence
              structure. One paraphrase swaps active for passive, one swaps
              quantifier choice, one swaps the politeness scaffolding, one
              shifts the framing from leading toward neutral, and one
              substitutes synonyms while keeping the meaning. Pairwise
              embedding similarity is checked after generation. Pairs above
              ninety five percent cosine similarity get rejected as collapsed
              and we regenerate. Pairs below seventy percent get rejected as
              divergent. Each paraphrase has to stay above eighty five percent
              cosine similarity with the original.
            </p>
            <p>
              For the actual probe, we sample two hundred personas from the
              audience pool and give each one the same question across all six
              wording variants. The persona prompt is the cached system
              message. The wording is the per call user message. With prompt
              caching turned on, the persona description is paid for once per
              persona and read for cents on every subsequent call against that
              same persona. That trade alone is what makes the probe affordable
              at scale.
            </p>
            <p>
              The result is a matrix shaped like persona by paraphrase index.
              Cell content is whatever the structured output tool returned: an
              integer for Likert, an integer for the choice index of single
              choice, a small array for multi choice. For a Likert question,
              the math is straightforward. Compute the response distribution
              under each paraphrase. Compute the Wasserstein distance between
              the original distribution and each paraphrase distribution.
              Report the largest one. Stack Cohen&apos;s d alongside it as an
              effect size, mostly so anyone reading the number knows whether
              one point five Wasserstein points means a real lift or a thin
              one.
            </p>
            <pre className="mt-4 rounded-md border border-[var(--color-border)] bg-black/40 p-4 overflow-x-auto text-[12px] leading-relaxed">
{`from scipy.stats import wasserstein_distance

original = responses[0]                  # integers, n=200
shifts = []
for k in range(1, len(paraphrases) + 1):
    paraphrase = responses[k]
    w = wasserstein_distance(original, paraphrase)
    d = cohens_d(original, paraphrase)
    shifts.append((k, w, d))

score = max(s[1] for s in shifts)
flag = "leading" if score > LEADING_THRESHOLD else "ok"`}
            </pre>
            <p>
              That is the core of it. The same structure gets reused for
              categorical questions with Jensen Shannon divergence in place of
              Wasserstein, since choice indices do not have an ordering you can
              treat as a real number line.
            </p>
          </Section>

          <H2>The two things that make it work</H2>
          <Section>
            <p>
              The personas are matched across paraphrases. We do not compute
              the original mean from one slice of the audience and the
              paraphrase mean from another. The two hundred personas in the
              sub swarm see every wording variant of every question, in
              isolation, with the same persona prompt cached as the system
              message. Without the matching, you cannot tell whether a shift
              comes from the wording or from a different demographic mix
              landing on the rephrased version. With the matching, the
              wording is the only thing that changed.
            </p>
            <p>
              The signal is sensitivity to perturbation, not response
              prediction. We are not claiming the personas predict what real
              panelists would answer. The recent literature on silicon
              sampling makes that claim hard to defend, and we do not need it
              for this particular detector to work. What we need is for the
              persona pool to react differently when the wording changes
              meaningfully and to react the same when the wording does not.
              That property is robust across model versions, persona prompt
              wording, and even decoding temperature within a reasonable
              range. The absolute response number is not robust. The
              difference between two response numbers under controlled wording
              perturbation is.
            </p>
            <p>
              You can see this by re running the same survey with a different
              persona prompt template. The absolute means shift, sometimes by
              half a point. The wording shift signal is roughly stable. That
              is the property the detector is built on.
            </p>
          </Section>

          <H2>What we gave up</H2>
          <Section>
            <p>
              This detector catches wording sensitivity. It does not, by
              itself, catch double barreled questions, loaded language,
              fatigue blocks, or the rest of the bias catalog we ship samples
              for. Each of those needs its own approach. Loaded language in
              particular is hard with this exact mechanic, since two
              paraphrases that both contain the loaded term will both pull in
              the same direction and the wording shift score will look small.
              Calibration on the held out injection corpus shows this clearly.
              The detector is recall one point oh on leading wording across
              all three severity levels and effectively zero on loaded
              language. We did not try to make the same detector cover both.
              The catalog page lists what is missing.
            </p>
            <p>
              Precision is the trade we made on this v0. The detector flags
              every leading question we plant, including subtle ones, and it
              also fires on a long tail of clean questions that it should not.
              That false positive rate is the threshold trade off, and the
              threshold itself is set against the calibration harness rather
              than picked from intuition. Tightening it is a v1 item. The
              alternative was missing real defects and producing reports that
              are wrong without making any noise about being wrong, which is
              the worst possible outcome for a tool researchers are supposed
              to trust.
            </p>
            <p>
              We also do not retroactively probe questions a researcher edits
              after the run. The cache is keyed on the question text, so an
              edit creates a new cache key and the old probe results are
              orphaned. For the workflow we built it for, this is fine.
              Researchers run pre flight after they have stopped iterating on
              wording. If editing in place became a workflow we cared about,
              the right thing is question level lineage, not letting the cache
              key drift.
            </p>
          </Section>

          <H2>Try it</H2>
          <Section>
            <p>
              The defect bearing sample is the cleanest place to see this in
              action. Open the report and expand Q4. The wording shift section
              shows the original mean of four point three two next to each of
              five neutral paraphrases averaging around three. The mechanism
              described above produced those numbers, end to end, on the
              precomputed sample.
            </p>
            <p>
              Source for the analyzer is at{" "}
              <code>preflight/stats/analyzers/paraphrase_shift.py</code>, the
              paraphrase generation lives at{" "}
              <code>preflight/worker/jobs/paraphrase_gen.py</code>, and the
              calibration that produces the recall and precision numbers is
              under <code>preflight/calibration/</code>. The repo is at{" "}
              <a
                href="https://github.com/krish1236/Knit-PreFlight"
                className="text-[var(--color-accent)] hover:underline"
              >
                krish1236/Knit-PreFlight
              </a>
              .
            </p>
          </Section>
        </article>
      </main>
    </div>
  );
}

function Section({ children }: { children: React.ReactNode }) {
  return <div className="mt-5 space-y-4 text-[15px] leading-7">{children}</div>;
}

function H2({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mt-12 text-lg font-semibold tracking-tight border-b border-[var(--color-border)] pb-2">
      {children}
    </h2>
  );
}
