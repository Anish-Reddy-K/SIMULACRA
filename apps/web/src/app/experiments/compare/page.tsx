"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError, Loading, Panel } from "@/components/lab/ui";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { expApi } from "@/lib/exp-api";
import { formatPercent } from "@/lib/format";
import { useApi } from "@/lib/use-api";

function Result({ a, b }: { a: number; b: number }) {
  const { data, error, loading, reload } = useApi(() => expApi.compareRuns(a, b), [a, b]);
  if (loading) return <Loading what="comparison" />;
  if (error || !data) return <ApiError error={error ?? "No data"} onRetry={reload} />;
  const d = data;
  return (
    <Panel as="h2" title={`Run #${d.run_a.id} (${d.run_a.model ?? "?"}, ${d.run_a.prompt ?? "?"}) vs run #${d.run_b.id} (${d.run_b.model ?? "?"}, ${d.run_b.prompt ?? "?"})`}>
      <dl className="grid grid-cols-2 gap-4 text-sm md:grid-cols-3">
        <div><dt className="text-xs text-muted-foreground">Matched trials</dt><dd className="font-medium">{d.matched_trials} (only in A: {d.only_in_a}, only in B: {d.only_in_b})</dd></div>
        <div><dt className="text-xs text-muted-foreground">Top-2-box A / B</dt><dd className="font-medium">{formatPercent(d.top2_a)} / {formatPercent(d.top2_b)}</dd></div>
        <div><dt className="text-xs text-muted-foreground">Same top-2-box answer for the same persona</dt><dd className="font-medium">{formatPercent(d.top2_agreement)}</dd></div>
        <div><dt className="text-xs text-muted-foreground">Cohen&apos;s kappa (chance-corrected agreement)</dt><dd className="font-medium">{d.top2_kappa == null ? "n/a" : d.top2_kappa.toFixed(2)}</dd></div>
        <div><dt className="text-xs text-muted-foreground">McNemar exact p</dt><dd className="font-medium">{d.mcnemar_p?.toFixed(3) ?? "n/a"}</dd></div>
        <div><dt className="text-xs text-muted-foreground">Same objection / exact intent</dt><dd className="font-medium">{formatPercent(d.objection_agreement)} / {formatPercent(d.intent_exact_agreement)}</dd></div>
      </dl>
      <ul className="mt-3 list-disc pl-5 text-xs text-muted-foreground">{d.notes.map((n) => (<li key={n}>{n}</li>))}</ul>
    </Panel>
  );
}

function Inner() {
  const router = useRouter();
  const params = useSearchParams();
  const ra = params.get("a"), rb = params.get("b");
  const [a, setA] = useState(ra ?? "");
  const [b, setB] = useState(rb ?? "");
  const valid = (v: string | null) => (v && /^\d+$/.test(v) ? Number(v) : null);
  return (
    <div className="flex flex-col gap-6">
      <Panel as="h2" title="Choose two runs">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm">Run A (id)<Input className="w-28" value={a} onChange={(e) => setA(e.target.value)} /></label>
          <label className="flex flex-col gap-1 text-sm">Run B (id)<Input className="w-28" value={b} onChange={(e) => setB(e.target.value)} /></label>
          <Button onClick={() => router.push(`/experiments/compare/?a=${a}&b=${b}`)} disabled={!valid(a) || !valid(b)}>Compare</Button>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">Compare runs of the same experiment design, for example two models or two prompt versions.</p>
      </Panel>
      {valid(ra) && valid(rb) && <Result a={valid(ra) as number} b={valid(rb) as number} />}
    </div>
  );
}

export default function Compare() {
  return (
    <>
      <PageHeader title="Compare runs" description="Measure how much two models, prompts or repeats disagree about the same simulated people." />
      <Suspense fallback={<p role="status">Loading...</p>}><Inner /></Suspense>
    </>
  );
}
