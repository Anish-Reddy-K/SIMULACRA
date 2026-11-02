import { describe, expect, it } from "vitest";
import { summarizeTargets } from "./compare";
import type { Metrics, Result } from "./lab-api";

const metrics = (over: Partial<Metrics>): Metrics => ({
  n: 10, concurrency: 1, wall_s: 60, valid_rate: 1, invalid_json_rate: 0, schema_mismatch_rate: 0,
  failure_rate: 0, timeout_rate: 0, valid_trials_per_min: 10, latency_ms_median: 1, latency_ms_p95: 2,
  ttft_ms_median: 1, decode_tokens_per_s_median: 50, decode_tps_method: "runtime_reported",
  prefill_tokens_per_s_median: null, peak_rss_mb: 2000, min_available_mb: 1000, swap_growth_mb: 0,
  first_request_ms: 100, ...over,
});

const result = (over: Partial<Result>): Result => ({
  id: 1, target_label: "a", runtime_kind: "ollama", runtime_version: null, base_url: "u", model: "m",
  model_digest: null, quantization: null, structured_mode: "constrained", stage: "quick",
  evidence: "quick", workload: "B", concurrency: 1, workload_hash: null, metrics: metrics({}),
  diagnostics: [], compat: null, extras: {}, ...over,
});

describe("summarizeTargets", () => {
  it("picks the best B throughput and its concurrency", () => {
    const [s] = summarizeTargets([
      result({ concurrency: 1, metrics: metrics({ valid_trials_per_min: 10 }) }),
      result({ id: 2, concurrency: 4, metrics: metrics({ valid_trials_per_min: 30 }) }),
    ]);
    expect(s.validPerMin).toBe(30);
    expect(s.concurrency).toBe(4);
  });
  it("averages only invariant diagnostics and never invents missing data", () => {
    const [s] = summarizeTargets([
      result({
        id: 3, workload: "F",
        diagnostics: [
          { name: "x", kind: "invariant", value: 1, n_valid: 1, n_total: 1, passed: true, detail: "" },
          { name: "y", kind: "invariant", value: 0.5, n_valid: 1, n_total: 1, passed: false, detail: "" },
          { name: "z", kind: "stability", value: 0, n_valid: 1, n_total: 1, passed: null, detail: "" },
        ],
      }),
    ]);
    expect(s.consistency).toBe(0.75);
    expect(s.soakDriftPct).toBeNull();
  });
  it("reports unmeasured targets as null", () => {
    const [s] = summarizeTargets([result({ workload: "compat", metrics: null })]);
    expect(s.validPerMin).toBeNull();
    expect(s.consistency).toBeNull();
    expect(s.peakRssMb).toBeNull();
  });
});
