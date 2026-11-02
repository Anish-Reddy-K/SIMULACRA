export type Hardware = {
  os: string;
  os_version: string;
  arch: string;
  chip: string | null;
  apple_silicon: boolean;
  cpu_cores_total: number | null;
  cpu_cores_performance: number | null;
  ram_total_mb: number;
  ram_available_mb: number;
  swap_used_mb: number;
  disk_free_mb: number;
  disk_total_mb: number;
  metal: string | null;
  on_battery: boolean | null;
  low_power_mode: boolean | null;
  sleep_prevented: boolean | null;
  notes: string[];
};

export type ModelInfo = {
  name: string;
  digest: string | null;
  size_bytes: number | null;
  parameter_size: string | null;
  quantization: string | null;
  family: string | null;
};

export type RuntimeReport = {
  base_url: string;
  running: boolean;
  problem: string | null;
  info: {
    kind: string;
    version: string | null;
    capabilities: {
      json_schema: boolean | null;
      reports_timings: boolean;
      parallel_slots: number | null;
      context_size: number | null;
    };
  } | null;
  models: ModelInfo[];
};

export type Discovery = {
  installed: { name: string; path: string | null }[];
  runtimes: RuntimeReport[];
};

export type Evidence = "screened" | "quick" | "detailed" | "soak";

export type ConfigEvidence = {
  key: string;
  label: string;
  runtime_kind: string;
  model: string;
  evidence: Evidence;
  valid_per_min: number | null;
  best_concurrency: number | null;
  decode_tokens_per_s: number | null;
  decode_tps_method: string | null;
  valid_rate: number | null;
  peak_rss_mb: number | null;
  consistency: number | null;
};

export type Recommendation = {
  goal: string;
  title: string;
  selected: ConfigEvidence | null;
  provisional: boolean;
  rationale: string[];
  considered: { label: string; status: string; detail: string }[];
  caveats: string[];
  when_different: string;
  policy_version: string;
};

export type RunSummary = {
  id: number;
  stage: string;
  status: string;
  created_at: string;
  finished_at: string | null;
  op: string | null;
  op_done: number;
  op_total: number;
  error: string | null;
  targets: { base_url: string; model: string; structured_mode: string }[];
};

export type Diagnostic = {
  name: string;
  kind: string;
  value: number | null;
  n_valid: number;
  n_total: number;
  passed: boolean | null;
  detail: string;
};

export type Metrics = {
  n: number;
  concurrency: number;
  wall_s: number;
  valid_rate: number;
  invalid_json_rate: number;
  schema_mismatch_rate: number;
  failure_rate: number;
  timeout_rate: number;
  valid_trials_per_min: number;
  latency_ms_median: number | null;
  latency_ms_p95: number | null;
  ttft_ms_median: number | null;
  decode_tokens_per_s_median: number | null;
  decode_tps_method: string;
  prefill_tokens_per_s_median: number | null;
  peak_rss_mb: number | null;
  min_available_mb: number | null;
  swap_growth_mb: number | null;
  first_request_ms: number | null;
};

export type Result = {
  id: number;
  target_label: string;
  runtime_kind: string;
  runtime_version: string | null;
  base_url: string;
  model: string;
  model_digest: string | null;
  quantization: string | null;
  structured_mode: string;
  stage: string;
  evidence: Evidence;
  workload: string;
  concurrency: number;
  workload_hash: string | null;
  metrics: Metrics | null;
  diagnostics: Diagnostic[];
  compat: { ok: boolean; error: string | null; structured_valid_rate: number | null } | null;
  extras: Record<string, unknown>;
};

export type RunDetail = {
  run: RunSummary;
  hardware: Hardware;
  results: Result[];
  events: string[];
};

export type Sample = {
  idx: number;
  group: string;
  status: string;
  text: string;
  error: string | null;
  total_ms: number;
  ttft_ms: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
};

const BASE = "/api/v1/lab";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init);
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // keep status text
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const labApi = {
  hardware: () => request<Hardware>("/hardware"),
  runtimes: () => request<Discovery>("/runtimes"),
  recommendations: () => request<Recommendation[]>("/recommendations"),
  runs: () => request<RunSummary[]>("/benchmarks"),
  run: (id: number) => request<RunDetail>(`/benchmarks/${id}`),
  samples: (runId: number, resultId: number) =>
    request<Sample[]>(`/benchmarks/${runId}/results/${resultId}/samples`),
  start: (body: {
    stage: string;
    soak_seconds: number;
    targets: { base_url: string; model: string; structured_mode: string }[];
  }) =>
    request<RunSummary>("/benchmarks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  cancel: (id: number) => request<{ status: string }>(`/benchmarks/${id}/cancel`, { method: "POST" }),
};
