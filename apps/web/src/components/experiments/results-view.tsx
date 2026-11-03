"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, BarChart, Loading, Panel } from "@/components/lab/ui";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { codeLabel, expApi, type Comparison, type Quote, type Results, type TrialDetail } from "@/lib/exp-api";
import { formatPercent } from "@/lib/format";
import { useApi } from "@/lib/use-api";

function TrialSource({ id }: { id: number }) {
  const { data, error, loading } = useApi<TrialDetail>(() => expApi.trial(id), [id]);
  if (loading) return <p role="status" className="text-xs">Loading source record...</p>;
  if (error || !data) return <p role="alert" className="text-xs text-destructive">{error}</p>;
  return (
    <div className="mt-2 rounded-lg border border-hairline bg-muted p-3 text-xs neu-inset">
      <p className="font-semibold">Source trial #{data.id} (persona {data.persona_id}, status {data.status}, {Math.round(data.latency_ms)} ms)</p>
      <p className="mt-2 font-semibold">Prompt sent to the model</p>
      <pre className="whitespace-pre-wrap font-mono">{data.prompt_text}</pre>
      <p className="mt-2 font-semibold">Raw model output</p>
      <pre className="whitespace-pre-wrap font-mono">{data.raw_output}</pre>
    </div>
  );
}

function QuoteItem({ q }: { q: Quote }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="flex flex-col gap-1 border-b border-hairline pb-3 text-sm">
      <span>&ldquo;{q.text}&rdquo;</span>
      <span className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="outline">{q.kind.replace("top_", "")}: {codeLabel(q.code)}</Badge>
        persona {q.persona_id}
        <Button variant="ghost" size="xs" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Hide source" : `Source trial #${q.trial_id}`}
        </Button>
      </span>
      {open && <TrialSource id={q.trial_id} />}
    </li>
  );
}

function ComparisonPanel({ runId }: { runId: number }) {
  const { data, error, loading } = useApi<Comparison>(() => expApi.comparison(runId), [runId]);
  if (loading) return <Loading what="comparison" />;
  if (error || !data) return <ApiError error={error ?? "No data"} />;
  if (data.pairs.length === 0) return null;
  const pct = (x?: number) => (x === undefined ? "n/a" : `${(x * 100).toFixed(0)}%`);
  const sig = data.segments.filter((x) => x.significant);
  return (
    <Panel as="h2" title="Treatment comparison">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Treatments compared with the baseline</caption>
          <thead>
            <tr className="border-b border-hairline">
              {["Treatment", "Top-2-box", "Baseline", "Difference", "Sampling variation of difference", "Holm-adjusted p", "Effect size (h)", "Result"].map((h) => (<th key={h} scope="col" className="py-1 pr-4">{h}</th>))}
            </tr>
          </thead>
          <tbody>
            {data.pairs.map((p) => (
              <tr key={p.treatment_idx} className="border-b border-hairline">
                <td className="py-2 pr-4 font-medium">{p.label}</td>
                <td className="pr-4">{pct(p.top2_treatment)}</td>
                <td className="pr-4">{pct(p.top2_baseline)} ({p.vs})</td>
                <td className="pr-4 font-mono">{p.diff === undefined ? "n/a" : `${p.diff >= 0 ? "+" : ""}${(p.diff * 100).toFixed(1)} pts`}</td>
                <td className="pr-4 font-mono text-xs">{p.diff_ci_low === undefined ? "paired test" : `${(p.diff_ci_low * 100).toFixed(0)} to ${((p.diff_ci_high ?? 0) * 100).toFixed(0)} pts`}</td>
                <td className="pr-4 font-mono">{p.p_holm === undefined ? "n/a" : p.p_holm.toFixed(3)}</td>
                <td className="pr-4 font-mono">{p.cohens_h === undefined ? "n/a" : p.cohens_h.toFixed(2)}</td>
                <td><Badge variant={p.significant ? "default" : "secondary"}>{p.significant ? "difference detected" : "no detectable difference"}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.pricing && (
        <div className="mt-6">
          <BarChart
            title="Simulated purchase interest by price (top-2-box)"
            hint={data.pricing.note}
            rows={data.pricing.curve.map((c) => ({ label: `$${c.price_usd}`, value: c.top2, text: `${pct(c.top2 ?? undefined)} (n=${c.n})` }))}
          />
          {data.pricing.monotone_violations.map((v) => (
            <Alert key={`${v.lower_price}-${v.higher_price}`} variant="warning" className="mt-3">
              <AlertTitle>Implausible pattern</AlertTitle>
              <AlertDescription>
                Simulated interest was higher at ${v.higher_price} than at ${v.lower_price} (p = {v.p.toFixed(3)}). Treat this as a model artifact, not a finding.
              </AlertDescription>
            </Alert>
          ))}
        </div>
      )}
      {data.balance && (
        <p className="mt-4 text-xs text-muted-foreground">
          Randomization balance: smallest Holm-adjusted p = {data.balance.min_p_holm?.toFixed(3)}{" "}
          {data.balance.imbalanced ? "(imbalance detected between groups)" : "(no detectable imbalance)"}. Group sizes:{" "}
          {Object.entries(data.balance.arm_sizes).map(([k, v]) => `${k}: ${v}`).join(", ")}.
        </p>
      )}
      {sig.length > 0 && (
        <p className="mt-2 text-xs text-muted-foreground">
          Exploratory: {sig.length} segment difference(s) remained significant after Holm adjustment across {data.segments.length} tests:{" "}
          {sig.map((x) => `${codeLabel(x.attribute)}=${codeLabel(x.value)}`).join(", ")}.
        </p>
      )}
      <ul className="mt-3 list-disc pl-5 text-xs text-muted-foreground">{data.notes.map((n) => (<li key={n}>{n}</li>))}</ul>
    </Panel>
  );
}

export function ResultsView({ runId }: { runId: number }) {
  const router = useRouter();
  const { data, error, loading, reload } = useApi<Results>(() => expApi.results(runId), [runId]);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  if (loading) return <Loading what="results" />;
  if (error || !data) return <ApiError error={error ?? "No data"} onRetry={reload} />;

  async function makeReport() {
    setBusy(true);
    setProblem(null);
    try {
      const rep = await expApi.createReport(runId);
      router.push(`/reports/view/?id=${rep.id}`);
    } catch (e) {
      setProblem(e instanceof Error ? e.message : "Could not create the report");
      setBusy(false);
    }
  }

  const t = data.totals;
  const segs = data.segments.filter((s) => !s.suppressed);
  const hidden = data.segments.length - segs.length;
  return (
    <div className="flex flex-col gap-6">
      <Alert role="note">
        <AlertTitle>Simulated results</AlertTitle>
        <AlertDescription>
          These are opinions from model-generated personas, not observed human behavior or validated predictions.
        </AlertDescription>
      </Alert>
      <Panel as="h2" title="Overview">
        <dl className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
          <div><dt className="text-xs text-muted-foreground">Trials</dt><dd className="font-medium">{t.trials} of {t.planned} planned</dd></div>
          <div><dt className="text-xs text-muted-foreground">Valid responses</dt><dd className="font-medium">{t.valid}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Invalid output</dt><dd className="font-medium">{formatPercent(t.invalid_rate)}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Statuses</dt><dd className="font-mono text-xs">{Object.entries(t.by_status).map(([k, v]) => `${k}:${v}`).join(" ")}</dd></div>
        </dl>
        <div className="mt-4 flex gap-3">
          <Button onClick={() => void makeReport()} disabled={busy || t.valid === 0}>{busy ? "Creating..." : "Create report"}</Button>
        </div>
        {problem && <p role="alert" className="mt-2 text-sm text-destructive">{problem}</p>}
      </Panel>

      {data.treatments.map((tr) => (
        <Panel as="h2" key={tr.idx} title={`${tr.label} (${tr.n_valid} valid)`}>
          <div className="grid gap-8 md:grid-cols-2">
            <BarChart
              title="Purchase intent"
              rows={tr.intent.map((i) => ({ label: codeLabel(i.code), value: i.share, text: `${i.n} (${formatPercent(i.share)})` }))}
            />
            <div className="flex flex-col gap-3 text-sm">
              <p>
                <span className="font-semibold">Top-2-box:</span> {formatPercent(tr.top2box.share)} ({tr.top2box.n} of {tr.top2box.of})
                <span className="block text-xs text-muted-foreground">
                  Sampling variation of this simulation: {formatPercent(tr.top2box.ci_low)} to {formatPercent(tr.top2box.ci_high)}. Not uncertainty about real people.
                </span>
              </p>
              <p><span className="font-semibold">Mean appeal:</span> {tr.appeal.mean === null ? "n/a" : `${tr.appeal.mean.toFixed(2)} of 5`}</p>
              <BarChart
                title="Main objection"
                rows={tr.objections.filter((o) => o.n > 0).map((o) => ({ label: codeLabel(o.code), value: o.share, text: `${o.n} (${formatPercent(o.share)})` }))}
              />
            </div>
          </div>
        </Panel>
      ))}

      <ComparisonPanel runId={runId} />

      <Panel as="h2" title="Segments">
        <p className="mb-3 text-xs text-muted-foreground">
          Top-2-box share (probably or definitely) by segment. {hidden} small segments (fewer than 10 valid responses) are hidden.
        </p>
        <div tabIndex={0} role="region" aria-label="Segment results (scrollable)" className="max-h-96 overflow-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Segment results</caption>
            <thead>
              <tr className="border-b border-hairline">
                {["Segment", "Treatment", "n", "Top-2-box", "Sampling variation"].map((h) => (<th key={h} scope="col" className="py-1 pr-4">{h}</th>))}
              </tr>
            </thead>
            <tbody>
              {segs.map((s) => (
                <tr key={`${s.attribute}-${s.value}-${s.treatment_idx}`} className="border-b border-hairline">
                  <td className="py-1 pr-4">{codeLabel(s.attribute)} = {codeLabel(s.value)}</td>
                  <td className="pr-4">{data.treatments.find((x) => x.idx === s.treatment_idx)?.label}</td>
                  <td className="pr-4">{s.n}</td>
                  <td className="pr-4">{formatPercent(s.top2box?.share)}</td>
                  <td className="font-mono text-xs">{formatPercent(s.top2box?.ci_low)} to {formatPercent(s.top2box?.ci_high)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel as="h2" title="Representative responses">
        <ul className="flex flex-col gap-3">{data.quotes.map((q) => (<QuoteItem key={`${q.kind}-${q.trial_id}`} q={q} />))}</ul>
      </Panel>

      <Panel as="h2" title="Contradictory patterns">
        {data.contradictions.length === 0 ? (
          <p className="text-sm text-muted-foreground">None detected by the configured checks.</p>
        ) : (
          <ul className="list-disc pl-5 text-sm">
            {data.contradictions.map((c, i) => (<li key={i}>{c.description}{c.n ? ` (n=${c.n})` : ""}</li>))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
