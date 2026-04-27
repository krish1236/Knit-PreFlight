/**
 * Typed client for the Pre-Flight backend.
 *
 * In dev, requests go through Next's /api/* rewrite to the FastAPI service.
 * In production, set NEXT_PUBLIC_API_BASE to the deployed API URL.
 */

export type Severity = "high" | "medium" | "low" | "none";

export interface SampleListing {
  slug: string;
  survey_id: string;
  title: string;
  objective: string;
  cached_run_id: string | null;
  cached_run_status: string | null;
}

export interface RunSampleResponse {
  run_id: string;
  cached: boolean;
  status: string;
}

export interface CreateRunResponse {
  run_id: string;
  status: string;
  stream_url: string;
}

export interface RunStateView {
  run_id: string;
  survey_id: string;
  status: string;
  is_sample: boolean;
  created_at: string;
  completed_at: string | null;
}

export interface ParaphraseExample {
  paraphrase_idx: number;
  text: string;
  mean_response: number;
  n: number;
}

export interface ParaphraseShiftFlag {
  question_id: string;
  metric: "wasserstein" | "jensen_shannon" | "total_variation" | "skipped";
  score: number;
  cohens_d: number | null;
  n_personas: number;
  severity: Severity;
  examples: ParaphraseExample[];
  note: string | null;
}

export interface IRTFlag {
  question_id: string;
  discrimination: number;
  interpretation: "poor" | "moderate" | "strong" | "experimental";
  convergence_ok: boolean;
  n_personas: number;
  severity: Severity;
  note: string | null;
}

export interface RedundancyFlag {
  q_id_a: string;
  q_id_b: string;
  pearson: number;
  spearman: number;
  n_personas: number;
  severity: Severity;
}

export interface ScreenerFlag {
  type:
    | "dead_branch"
    | "loop"
    | "unreachable_question"
    | "contradicting_rule"
    | "self_loop";
  description: string;
  evidence: Record<string, unknown>;
  severity: Severity;
}

export interface QuotaFeasibility {
  cell: Record<string, unknown>;
  target_n: number;
  estimated_panel_pct: number;
  estimated_n_at_target: number;
  severity: Severity;
}

export interface QuestionFlags {
  question_id: string;
  question_text: string;
  type: string;
  severity: Severity;
  paraphrase_shift: ParaphraseShiftFlag | null;
  irt: IRTFlag | null;
}

export interface CalibrationDisclosure {
  f1_overall: number | null;
  benchmark: string;
  version: string;
}

export interface ReportCard {
  run_id: string;
  survey_id: string;
  completed_at: string;
  calibration: CalibrationDisclosure;
  per_question: QuestionFlags[];
  redundancy_pairs: RedundancyFlag[];
  screener_issues: ScreenerFlag[];
  quota_feasibility: QuotaFeasibility[];
  estimated_panel_exposure: {
    high_severity_questions: number;
    medium_severity_questions: number;
    flagged_question_count: number;
    method: string;
  };
  framing_disclaimer: string;
}

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(res.status, text);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listSamples: () => request<SampleListing[]>("/samples"),
  runSample: (slug: string) =>
    request<RunSampleResponse>(`/samples/${slug}/run`, { method: "POST" }),
  createRun: (survey: unknown, quickMode = false) =>
    request<CreateRunResponse>("/runs", {
      method: "POST",
      body: JSON.stringify({ survey, quick_mode: quickMode }),
    }),
  getRun: (runId: string) => request<RunStateView>(`/runs/${runId}`),
  getReport: (runId: string) => request<ReportCard>(`/runs/${runId}/report`),
};

export { ApiError };
