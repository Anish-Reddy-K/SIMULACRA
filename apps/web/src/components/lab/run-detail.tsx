"use client";

import { useState } from "react";
import { ApiError, BarChart, EvidenceBadge, Fact, Loading, Panel } from "@/components/lab/ui";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { summarizeTargets } from "@/lib/compare";
import { formatMb, formatNumber, formatPercent } from "@/lib/format";
import { labApi, type Result, type Sample } from "@/lib/lab-api";
import { useApi } from "@/lib/use-api";

function SamplesViewer({ runId, result }: { runId: number; result: Result }) {
  const { data, error, loading } = useApi(() => labApi.samples(runId, result.id), [runId, result.id]);
  if (loading) return <Loading what="samples" />;
  if (error || !data) return <ApiError error={error ?? "No data"} />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <caption className="sr-only">Raw trials behind this measurement</caption>
        <thead>
          <tr className="border-b border-hairline">
            <th scope="col" className="py-1 pr-3">#</th>
            <th scope="col" className="pr-3">Group</th>
            <th scope="col" className="pr-3">Status</th>
            <th scope="col" className="pr-3">ms</th>
            <th scope="col" className="pr-3">Tokens out</th>
            <th scope="col">Response</th>
          </tr>
        </thead>
        <tbody>
          {data.map((s: Sample) => (
            <tr key={s.idx} className="border-b border-hairline align-top">
              <td className="py-1 pr-3 font-mono">{s.idx}</td>
              <td className="pr-3">{s.group}</td>
              <td className="pr-3">
                <Badge variant={s.status === "valid" ? "secondary" : "warning"}>{s.status.replace(/_/g, " ")}</Badge>
              </td>
              <td className="pr-3 font-mono">{Math.round(s.total_ms)}</td>
              <td className="pr-3 font-mono">{s.completion_tokens ?? "-"}</td>
              <td className="max-w-md break-words font-mono">{s.error ?? s.text}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RunDetailView({ runId }: { runId: number }) {
  const { data, error, loading, reload } = useApi(() => labApi.run(runId), [runId]);
  const [open, setOpen] = useState<number | null>(null);
  if (loading) return <Loading what="results" />;
  if (error || !data) return <ApiError error={error ?? "No data"} onRetry={reload} />;
  const { run, results, hardware, events } = data;
  const summaries = summarizeTargets(results).filter((s) => s.validPerMin !== null);
  const measuredResults = results.filter((r) => r.metrics);

  const hasMock = results.some((r) => r.runtime_kind === "mock");

  return (
    <div className="flex flex-col gap-6">
      {hasMock && (
        <Alert variant="warning" role="note">
          <AlertTitle>Synthetic test data</AlertTitle>
          <AlertDescription>
            This run used the built-in mock backend. These numbers are not measurements of any real
            model and are never used for recommendations.
          </AlertDescription>
        </Alert>
      )}
      <Panel as="h2" title={`Benchmark #${run.id}`}>
        <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Fact label="Stage" value={run.stage} />
          <Fact label="Status" value={run.status.replace(/_/g, " ")} warn={run.status !== "completed"} />
          <Fact label="Started" value={new Date(run.created_at).toLocaleString()} />
          <Fact label="Machine" value={`${hardware.chip ?? hardware.arch}, ${formatMb(hardware.ram_total_mb)}`} />
        </dl>
        {run.error && <p className="mt-3 text-sm text-destructive">{run.error}</p>}
      </Panel>

      {summaries.length > 0 ? (
        <Panel as="h2" title="Comparison">
          <div className="mb-4 flex flex-wrap gap-2">
            {summaries.map((s) => (
              <span key={s.label} className="flex items-center gap-2 text-xs">
                <span className="font-mono">{s.label}</span>
                <EvidenceBadge level={s.evidence} />
              </span>
            ))}
          </div>
          <div className="grid gap-8 md:grid-cols-2">
            <BarChart
              title="Valid trials per minute (higher is better)"
              hint="Primary metric: structured, schema-valid persona decisions completed per minute at the best tested concurrency."
              rows={summaries.map((s) => ({
                label: s.label, value: s.validPerMin,
                text: `${formatNumber(s.validPerMin, 1)} at c=${s.concurrency}`,
              }))}
            />
            <BarChart
              title="Decode tokens per second"
              hint="Per request. Runtime-reported where available, otherwise derived on the client (marked)."
              rows={summaries.map((s) => ({
                label: s.label, value: s.decodeTps,
                text: s.decodeTps ? `${formatNumber(s.decodeTps, 0)} (${s.tpsMethod === "runtime_reported" ? "runtime" : "derived"})` : "not measured",
              }))}
            />
            <BarChart
              title="Peak server memory (lower is better)"
              hint="Server process tree RSS. GPU allocations may be under-reported on Apple Silicon."
              rows={summaries.map((s) => ({ label: s.label, value: s.peakRssMb, text: formatMb(s.peakRssMb) }))}
            />
            <BarChart
              title="Valid structured-output rate"
              rows={summaries.map((s) => ({ label: s.label, value: s.validRate, text: formatPercent(s.validRate) }))}
            />
            <BarChart
              title="Behavioral consistency (invariants passed)"
              hint="Proxy checks on synthetic cases. They do not show the model resembles real people."
              rows={summaries.map((s) => ({ label: s.label, value: s.consistency, text: formatPercent(s.consistency) }))}
            />
            <BarChart
              title="Sustained throughput vs start of run"
              hint="Only available if a sustained run was done."
              rows={summaries.map((s) => ({
                label: s.label, value: s.soakDriftPct,
                text: s.soakDriftPct === null ? "not tested" : `${s.soakDriftPct.toFixed(0)}%`,
              }))}
            />
          </div>
        </Panel>
      ) : (
        <Panel as="h2" title="Comparison">
          <p className="text-sm text-muted-foreground">
            This run has no performance measurements (for example a compatibility check only), so
            there is nothing to compare or recommend.
          </p>
        </Panel>
      )}

      {results.filter((r) => r.diagnostics.length > 0).map((r) => (
        <Panel key={r.id} title={`Consistency diagnostics: ${r.target_label}`}>
          <ul className="flex flex-col gap-2 text-sm">
            {r.diagnostics.map((d) => (
              <li key={d.name} className="flex flex-wrap items-baseline justify-between gap-2">
                <span>
                  <span className="font-medium">{d.name.replace(/_/g, " ")}</span>{" "}
                  <span className="text-xs text-muted-foreground">({d.kind}, {d.n_valid} valid of {d.n_total})</span>
                  <span className="block text-xs text-muted-foreground">{d.detail}</span>
                </span>
                <span className="flex items-center gap-2">
                  <span className="font-mono">{formatPercent(d.value)}</span>
                  {d.passed !== null && <Badge variant={d.passed ? "secondary" : "warning"}>{d.passed ? "pass" : "fail"}</Badge>}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      ))}

      <Panel as="h2" title="All measurements">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <caption className="sr-only">Every measurement in this run</caption>
            <thead>
              <tr className="border-b border-hairline">
                {["Target", "Workload", "Conc.", "n", "Valid", "Valid/min", "Latency median", "p95", "TTFT", "Failures", "Evidence", ""].map((h) => (
                  <th key={h} scope="col" className="py-1 pr-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {measuredResults.map((r) => {
                const m = r.metrics!;
                return (
                  <tr key={r.id} className="border-b border-hairline">
                    <td className="py-1 pr-3 font-mono">{r.target_label}</td>
                    <td className="pr-3">{r.workload}</td>
                    <td className="pr-3">{r.concurrency}</td>
                    <td className="pr-3">{m.n}</td>
                    <td className="pr-3">{formatPercent(m.valid_rate)}</td>
                    <td className="pr-3">{formatNumber(m.valid_trials_per_min, 1)}</td>
                    <td className="pr-3">{m.latency_ms_median ? `${Math.round(m.latency_ms_median)} ms` : "-"}</td>
                    <td className="pr-3">{m.latency_ms_p95 ? `${Math.round(m.latency_ms_p95)} ms` : "-"}</td>
                    <td className="pr-3">{m.ttft_ms_median ? `${Math.round(m.ttft_ms_median)} ms` : "-"}</td>
                    <td className="pr-3">{formatPercent(m.failure_rate)}</td>
                    <td className="pr-3">{r.evidence}</td>
                    <td>
                      <Button variant="ghost" size="xs" aria-expanded={open === r.id} onClick={() => setOpen(open === r.id ? null : r.id)}>
                        {open === r.id ? "Hide trials" : "Inspect trials"}
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {open !== null && (
          <div className="mt-4">
            <SamplesViewer runId={run.id} result={results.find((r) => r.id === open)!} />
          </div>
        )}
      </Panel>

      <Panel as="h2" title="Exact configuration">
        <ul className="flex flex-col gap-1 font-mono text-xs">
          {[...new Map(results.map((r) => [r.target_label, r])).values()].map((r) => (
            <li key={r.id}>
              {r.runtime_kind} {r.runtime_version ?? "?"} | {r.model} | digest {r.model_digest?.slice(0, 12) ?? "n/a"} | quant {r.quantization ?? "n/a"} | json {r.structured_mode} | {r.base_url}
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-muted-foreground">
          Workload hashes: {[...new Set(measuredResults.map((r) => `${r.workload}:${r.workload_hash}`))].join("  ")}
        </p>
      </Panel>

      <Panel as="h2" title="Activity log">
        <ul className="flex flex-col gap-1 font-mono text-xs">
          {events.map((e, i) => (
            <li key={`${i}-${e}`}>{e}</li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
