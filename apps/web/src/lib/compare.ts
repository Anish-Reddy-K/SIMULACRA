import type { Result } from "@/lib/lab-api";

export type TargetSummary = {
  label: string;
  evidence: string;
  validPerMin: number | null;
  concurrency: number | null;
  decodeTps: number | null;
  tpsMethod: string | null;
  peakRssMb: number | null;
  validRate: number | null;
  consistency: number | null;
  soakDriftPct: number | null;
};

const ORDER = ["screened", "quick", "detailed", "soak"];

/** One summary per target label, computed only from stored results (no estimates). */
export function summarizeTargets(results: Result[]): TargetSummary[] {
  const labels = [...new Set(results.map((r) => r.target_label))];
  return labels.map((label) => {
    const rows = results.filter((r) => r.target_label === label);
    const b = rows
      .filter((r) => r.workload === "B" && r.metrics)
      .sort((a, c) => (c.metrics?.valid_trials_per_min ?? 0) - (a.metrics?.valid_trials_per_min ?? 0));
    const best = b[0]?.metrics ?? null;
    const measured = rows.filter((r) => r.metrics && r.workload !== "G");
    const total = measured.reduce((n, r) => n + (r.metrics?.n ?? 0), 0);
    const validRate = total
      ? measured.reduce((n, r) => n + (r.metrics?.valid_rate ?? 0) * (r.metrics?.n ?? 0), 0) / total
      : null;
    const peaks = measured.map((r) => r.metrics?.peak_rss_mb).filter((v): v is number => v != null);
    const f = rows.filter((r) => r.workload === "F" && r.diagnostics.length).at(-1);
    const inv = f?.diagnostics.filter((d) => d.kind === "invariant" && d.value !== null) ?? [];
    const g = rows.find((r) => r.workload === "G");
    const drift = g?.extras["throughput_drift"];
    return {
      label,
      evidence: rows.map((r) => r.evidence).sort((x, y) => ORDER.indexOf(y) - ORDER.indexOf(x))[0],
      validPerMin: best?.valid_trials_per_min ?? null,
      concurrency: b[0]?.concurrency ?? null,
      decodeTps: best?.decode_tokens_per_s_median ?? null,
      tpsMethod: best?.decode_tps_method ?? null,
      peakRssMb: peaks.length ? Math.max(...peaks) : null,
      validRate,
      consistency: inv.length ? inv.reduce((n, d) => n + (d.value ?? 0), 0) / inv.length : null,
      soakDriftPct: typeof drift === "number" ? drift * 100 : null,
    };
  });
}
