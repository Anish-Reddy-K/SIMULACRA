"use client";

import { useState } from "react";
import { ApiError, BarChart, Loading, Panel } from "@/components/lab/ui";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { codeLabel, expApi, type QueryResult, type Synthesis, type Themes } from "@/lib/exp-api";
import { formatPercent } from "@/lib/format";
import { useApi } from "@/lib/use-api";

const ATTRIBUTES = ["age_band", "income_band", "region", "gender", "education", "employment", "household", "tech_adoption", "price_sensitivity"];
const INTENTS = ["definitely", "probably", "unsure", "probably_not", "definitely_not"];
const OBJECTIONS = ["price", "trust", "need", "complexity", "privacy", "already_have_alternative", "other"];

function Field({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1 text-sm">
      <label htmlFor={id}>{label}</label>
      {children}
    </div>
  );
}

function EvidenceLinks({ ids, onOpen }: { ids: number[]; onOpen?: (id: number) => void }) {
  return (
    <span className="flex flex-wrap gap-1">
      {ids.map((id) => (
        <Button key={id} variant="ghost" size="xs" onClick={() => onOpen?.(id)} aria-label={`Open source trial ${id}`}>
          trial #{id}
        </Button>
      ))}
    </span>
  );
}

export function SynthesisPanel({ runId, onOpenTrial }: { runId: number; onOpenTrial?: (id: number) => void }) {
  const { data, error, loading, reload } = useApi<Synthesis>(() => expApi.synthesis(runId), [runId]);
  if (loading) return <Loading what="findings" />;
  if (error || !data) return <ApiError error={error ?? "No data"} onRetry={reload} />;
  const verified = new Map(data.verification.map((v) => [v.id, v]));
  return (
    <Panel as="h2" title="Key findings with evidence">
      <p className="mb-3 text-xs text-muted-foreground">
        Each finding is generated from computed numbers (not written by a model), checked against the stored trials, and linked to example source records.
      </p>
      <ul className="flex flex-col gap-3">
        {data.claims.map((c) => {
          const v = verified.get(c.id);
          return (
            <li key={c.id} className="flex flex-col gap-1 border-b border-hairline pb-3 text-sm">
              <span>{c.text}</span>
              <span className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <Badge variant={v?.verified ? "secondary" : "warning"}>{v?.verified ? "verified against stored trials" : "not verified"}</Badge>
                <EvidenceLinks ids={c.evidence_trial_ids} onOpen={onOpenTrial} />
              </span>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

export function ThemesPanel({ runId, onOpenTrial }: { runId: number; onOpenTrial?: (id: number) => void }) {
  const { data, error, loading, reload } = useApi<Themes>(() => expApi.themes(runId), [runId]);
  if (loading) return <Loading what="themes" />;
  if (error || !data) return <ApiError error={error ?? "No data"} onRetry={reload} />;
  return (
    <Panel as="h2" title="Themes in the free-text reasons">
      <p className="mb-3 text-xs text-muted-foreground">{data.note}</p>
      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-semibold">Distinctive words by main objection</h3>
          <ul className="flex flex-col gap-1 text-sm">
            {Object.entries(data.by_objection).map(([code, terms]) => (
              <li key={code}>
                <span className="font-medium">{codeLabel(code)}:</span>{" "}
                {terms.length ? terms.map((t) => `${t.term} (${t.count})`).join(", ") : <span className="text-muted-foreground">too little text</span>}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold">Recurring reasons (grouped by wording)</h3>
          <ul className="flex flex-col gap-2 text-sm">
            {data.clusters.slice(0, 6).map((c) => (
              <li key={c.exemplar_trial_id}>
                <span className="font-medium">{c.size} responses:</span> &ldquo;{c.exemplar_text}&rdquo;{" "}
                <EvidenceLinks ids={[c.exemplar_trial_id]} onOpen={onOpenTrial} />
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Panel>
  );
}

export function QueryPanel({ runId, treatments, onOpenTrial }: { runId: number; treatments: { idx: number; label: string }[]; onOpenTrial?: (id: number) => void }) {
  const [metric, setMetric] = useState("top2_share");
  const [groupBy, setGroupBy] = useState("income_band");
  const [treatment, setTreatment] = useState("");
  const [filterAttr, setFilterAttr] = useState("");
  const [filterValue, setFilterValue] = useState("");
  const [code, setCode] = useState("price");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function ask() {
    setBusy(true);
    setError(null);
    const params: Record<string, string> = { metric };
    if (groupBy) params.group_by = groupBy;
    if (treatment) params.treatment = treatment;
    if (filterAttr && filterValue) params[`filter_${filterAttr}`] = filterValue;
    if (metric === "objection_share" || metric === "intent_share") params.code = code;
    try {
      setResult(await expApi.query(runId, params));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Query failed");
    } finally {
      setBusy(false);
    }
  }

  const select = "h-10 rounded-lg border border-input bg-card px-2 text-sm";
  return (
    <Panel as="h2" title="Ask a question of the data">
      <p className="mb-3 text-xs text-muted-foreground">
        Structured questions are answered by computing over the stored trials. Nothing is sent to a model.
      </p>
      <div className="grid gap-3 md:grid-cols-3">
        <Field id="q-what-to-measure" label="What to measure"><select id="q-what-to-measure" className={select} value={metric} onChange={(e) => setMetric(e.target.value)}>
            <option value="top2_share">Share who would probably or definitely buy</option>
            <option value="appeal_mean">Average appeal (1-5)</option>
            <option value="objection_share">Share giving a specific objection</option>
            <option value="intent_share">Share with a specific intent</option>
            <option value="count">Number of responses</option>
          </select></Field>
        {metric === "objection_share" && (
          <Field id="q-objection" label="Objection"><select id="q-objection" className={select} value={code} onChange={(e) => setCode(e.target.value)}>{OBJECTIONS.map((o) => (<option key={o} value={o}>{codeLabel(o)}</option>))}</select></Field>
        )}
        {metric === "intent_share" && (
          <Field id="q-intent" label="Intent"><select id="q-intent" className={select} value={INTENTS.includes(code) ? code : "probably"} onChange={(e) => setCode(e.target.value)}>{INTENTS.map((o) => (<option key={o} value={o}>{codeLabel(o)}</option>))}</select></Field>
        )}
        <Field id="q-break-down-by" label="Break down by"><select id="q-break-down-by" className={select} value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
            <option value="">Everyone</option>{ATTRIBUTES.map((a) => (<option key={a} value={a}>{codeLabel(a)}</option>))}
          </select></Field>
        <Field id="q-treatment" label="Treatment"><select id="q-treatment" className={select} value={treatment} onChange={(e) => setTreatment(e.target.value)}>
            <option value="">All</option>{treatments.map((t) => (<option key={t.idx} value={t.idx}>{t.label}</option>))}
          </select></Field>
        <Field id="q-only-people-where" label="Only people where"><select id="q-only-people-where" className={select} value={filterAttr} onChange={(e) => setFilterAttr(e.target.value)}>
            <option value="">(no filter)</option>{ATTRIBUTES.map((a) => (<option key={a} value={a}>{codeLabel(a)}</option>))}
          </select></Field>
        {filterAttr && (
          <label className="flex flex-col gap-1 text-sm">equals
            <input className={select} value={filterValue} onChange={(e) => setFilterValue(e.target.value)} placeholder="e.g. west or 30-44" />
          </label>
        )}
      </div>
      <div className="mt-3"><Button onClick={() => void ask()} disabled={busy}>{busy ? "Computing..." : "Compute answer"}</Button></div>
      {error && <p role="alert" className="mt-2 text-sm text-destructive">{error}</p>}
      {result && (
        <div className="mt-4">
          <BarChart
            title={`${result.metric.replace(/_/g, " ")}${result.group_by ? ` by ${codeLabel(result.group_by)}` : ""}`}
            rows={result.rows.map((r) => ({
              label: `${codeLabel(r.group)} (n=${r.n})`,
              value: r.suppressed ? null : (result.metric === "appeal_mean" ? (r.value ?? 0) / 5 : result.metric === "count" ? null : (r.value ?? null)),
              text: r.suppressed ? "hidden: too few responses" : result.metric === "appeal_mean" ? `${(r.value ?? 0).toFixed(2)} of 5` : result.metric === "count" ? String(r.value) : `${formatPercent(r.value)} (${formatPercent(r.ci_low)} to ${formatPercent(r.ci_high)})`,
            }))}
          />
          <ul className="mt-3 flex flex-col gap-1 text-xs text-muted-foreground">
            {result.rows.filter((r) => !r.suppressed).map((r) => (
              <li key={r.group} className="flex flex-wrap items-center gap-2">{codeLabel(r.group)} evidence: <EvidenceLinks ids={r.evidence_trial_ids} onOpen={onOpenTrial} /></li>
            ))}
          </ul>
          <ul className="mt-2 list-disc pl-5 text-xs text-muted-foreground">{result.notes.map((n) => (<li key={n}>{n}</li>))}</ul>
        </div>
      )}
    </Panel>
  );
}
