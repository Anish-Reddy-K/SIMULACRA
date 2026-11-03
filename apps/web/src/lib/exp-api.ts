export type Experiment = {
  id: number;
  name: string;
  kind: string;
  research_question: string;
  hypothesis: string;
  population_version_id: number;
  scenario: Record<string, unknown>;
  config: Record<string, unknown>;
  treatments: { idx: number; label: string; params: Record<string, unknown> }[];
  created_at: string;
};

export type Share = { n: number; of: number; share: number | null; ci_low: number; ci_high: number };

export type TreatmentResult = {
  idx: number;
  label: string;
  n_trials: number;
  n_valid: number;
  intent: { code: string; n: number; share: number | null }[];
  top2box: Share;
  bottom2box: Share;
  appeal: { mean: number | null; sd: number | null; n: number };
  benefits: { code: string; n: number; share: number | null }[];
  objections: { code: string; n: number; share: number | null }[];
};

export type Segment = {
  attribute: string;
  value: string;
  treatment_idx: number;
  n: number;
  suppressed: boolean;
  top2box?: Share;
  appeal_mean?: number;
};

export type Quote = {
  kind: string;
  code: string;
  trial_id: number;
  persona_id: string;
  treatment_idx: number;
  text: string;
};

export type Results = {
  run_id: number;
  totals: { trials: number; valid: number; by_status: Record<string, number>; invalid_rate: number | null; planned: number };
  treatments: TreatmentResult[];
  segments: Segment[];
  objections: { code: string; n: number; share: number | null }[];
  benefits: { code: string; n: number; share: number | null }[];
  quotes: Quote[];
  contradictions: { kind: string; n?: number; description: string; example_trial_ids?: number[] }[];
  notes: string[];
};

export type ReportSummary = { id: number; run_id: number; title: string; created_at: string };

export type ReportFull = {
  id: number;
  title: string;
  generated_at: string;
  research_question: string;
  hypothesis: string;
  summary: string[];
  analysis: Results;
  manifest: Record<string, unknown>;
  limitations: string[];
  follow_up: string[];
};

export type TrialDetail = {
  id: number;
  run_id: number;
  persona_id: string;
  treatment_idx: number;
  status: string;
  attempts: number;
  parsed: Record<string, unknown> | null;
  latency_ms: number;
  prompt_text: string;
  raw_output: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/v1${path}`, init);
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
      else if (body.detail) detail = JSON.stringify(body.detail).slice(0, 300);
    } catch {
      // keep status
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const expApi = {
  list: () => request<Experiment[]>("/experiments"),
  get: (id: number) => request<Experiment>(`/experiments/${id}`),
  create: (body: unknown) => request<Experiment>("/experiments", json(body)),
  start: (id: number, body: unknown) =>
    request<{ run_id: number; trials_planned: number; state: string }>(`/experiments/${id}/start`, json(body)),
  results: (runId: number) => request<Results>(`/runs/${runId}/results`),
  trial: (id: number) => request<TrialDetail>(`/trials/${id}`),
  createReport: (runId: number) => request<ReportSummary>(`/runs/${runId}/reports`, { method: "POST" }),
  reports: () => request<ReportSummary[]>("/reports"),
  report: (id: number) => request<ReportFull>(`/reports/${id}`),
  exportUrl: (id: number, format: "md" | "html" | "json") => `/api/v1/reports/${id}/export?format=${format}`,
};

export function codeLabel(code: string): string {
  return code.replace(/_/g, " ");
}
