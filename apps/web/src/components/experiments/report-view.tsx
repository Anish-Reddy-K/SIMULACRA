"use client";

import { ApiError, Loading, Panel } from "@/components/lab/ui";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { codeLabel, expApi, type ReportFull } from "@/lib/exp-api";
import { formatPercent } from "@/lib/format";
import { useApi } from "@/lib/use-api";

export function ReportView({ id }: { id: number }) {
  const { data, error, loading, reload } = useApi<ReportFull>(() => expApi.report(id), [id]);
  if (loading) return <Loading what="report" />;
  if (error || !data) return <ApiError error={error ?? "No data"} onRetry={reload} />;
  const a = data.analysis;
  const m = data.manifest as Record<string, Record<string, unknown> | number | string>;
  const inf = (m.inference ?? {}) as Record<string, unknown>;
  return (
    <div className="flex flex-col gap-6">
      <Alert role="note">
        <AlertTitle>Simulated results</AlertTitle>
        <AlertDescription>Not observed human behavior and not a validated prediction. Read the limitations below.</AlertDescription>
      </Alert>
      <div className="flex flex-wrap gap-2">
        {(["md", "html", "json"] as const).map((f) => (
          <a key={f} className={buttonVariants({ variant: "outline", size: "sm" })} href={expApi.exportUrl(id, f)} download>
            Export {f === "md" ? "Markdown" : f.toUpperCase()}
          </a>
        ))}
      </div>
      <Panel as="h2" title="Executive summary">
        <ul className="list-disc pl-5 text-sm">{data.summary.map((s) => (<li key={s}>{s}</li>))}</ul>
      </Panel>
      <Panel as="h2" title="Research question">
        <p className="text-sm">{data.research_question}</p>
        {data.hypothesis && <p className="mt-2 text-sm text-muted-foreground">Hypothesis: {data.hypothesis}</p>}
      </Panel>
      <Panel as="h2" title="Inference model and runtime">
        <p className="font-mono text-xs">
          {String(inf.runtime)} {String(inf.runtime_version ?? "")} | {String(inf.model)} | digest {String(inf.model_digest ?? "n/a").slice(0, 12)} | temperature {String(inf.temperature)} | seed {String(inf.seed)}
        </p>
      </Panel>
      {a.treatments.map((tr) => (
        <Panel as="h2" key={tr.idx} title={`Findings: ${tr.label}`}>
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Purchase intent for {tr.label}</caption>
            <thead><tr className="border-b border-hairline"><th scope="col" className="py-1">Purchase intent</th><th scope="col">n</th><th scope="col">Share</th></tr></thead>
            <tbody>
              {tr.intent.map((i) => (<tr key={i.code} className="border-b border-hairline"><td className="py-1">{codeLabel(i.code)}</td><td>{i.n}</td><td>{formatPercent(i.share)}</td></tr>))}
            </tbody>
          </table>
        </Panel>
      ))}
      <Panel as="h2" title="Top objections">
        <ul className="list-disc pl-5 text-sm">{a.objections.map((o) => (<li key={o.code}>{codeLabel(o.code)}: {o.n} ({formatPercent(o.share)})</li>))}</ul>
      </Panel>
      <Panel as="h2" title="Representative responses">
        <ul className="flex flex-col gap-2 text-sm">
          {a.quotes.map((q) => (
            <li key={`${q.kind}-${q.trial_id}`}>&ldquo;{q.text}&rdquo; <span className="text-xs text-muted-foreground">({codeLabel(q.code)}; source trial #{q.trial_id}, persona {q.persona_id})</span></li>
          ))}
        </ul>
      </Panel>
      <Panel as="h2" title="Limitations">
        <ul className="list-disc pl-5 text-sm">{data.limitations.map((l) => (<li key={l}>{l}</li>))}</ul>
      </Panel>
      <Panel as="h2" title="Suggested real-world follow-up">
        <ul className="list-disc pl-5 text-sm">{data.follow_up.map((l) => (<li key={l}>{l}</li>))}</ul>
      </Panel>
      <Panel as="h2" title="Reproducibility metadata">
        <pre tabIndex={0} aria-label="Reproducibility metadata (scrollable)" className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg border border-hairline bg-muted p-3 font-mono text-xs neu-inset">{JSON.stringify(data.manifest, null, 2)}</pre>
      </Panel>
    </div>
  );
}
