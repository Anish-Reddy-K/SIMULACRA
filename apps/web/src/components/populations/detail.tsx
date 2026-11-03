"use client";

import { useEffect, useState } from "react";
import { ApiError, Loading, Panel } from "@/components/lab/ui";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatPercent } from "@/lib/format";
import { popApi, type Diagnostics, type Persona } from "@/lib/pop-api";
import { useApi } from "@/lib/use-api";

function Marginals({ d }: { d: Diagnostics }) {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      {d.marginals.map((m) => (
        <figure key={m.attribute} className="flex flex-col gap-2">
          <figcaption className="text-sm font-semibold">
            {m.attribute.replace(/_/g, " ")}{" "}
            <span className="font-normal text-muted-foreground">(largest gap {formatPercent(m.max_abs_diff)})</span>
          </figcaption>
          <ul className="flex flex-col gap-1.5">
            {Object.keys(m.target).map((k) => (
              <li key={k} className="flex flex-col gap-0.5">
                <div className="flex justify-between text-xs">
                  <span>{k.replace(/_/g, " ")}</span>
                  <span className="font-mono">target {formatPercent(m.target[k])} - realized {formatPercent(m.realized[k])}</span>
                </div>
                <div aria-hidden="true" className="relative h-3 rounded-full border border-hairline bg-muted">
                  <div className="absolute inset-y-0 left-0 rounded-full bg-primary" style={{ width: `${m.realized[k] * 100}%` }} />
                  <div className="absolute inset-y-0 border-r-2 border-foreground" style={{ left: `${m.target[k] * 100}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </figure>
      ))}
    </div>
  );
}

function DiagnosticsView({ d }: { d: Diagnostics }) {
  return (
    <div className="flex flex-col gap-6">
      <Panel title="Fidelity to the assumed distribution">
        <p className="mb-4 text-xs text-muted-foreground">
          Bars show realized shares; the vertical line marks the target. This checks the sampler
          against the spec you chose, not against any real population.
        </p>
        <Marginals d={d} />
      </Panel>
      <Panel title="Correlations">
        {d.correlations.length === 0 ? (
          <p className="text-sm text-muted-foreground">No correlations were specified.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Target and realized correlations</caption>
            <thead>
              <tr className="border-b border-hairline">
                {["Pair", "Target", "Realized (Spearman)", "Gap"].map((h) => (
                  <th key={h} scope="col" className="py-1 pr-4">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {d.correlations.map((c) => (
                <tr key={`${c.a}-${c.b}`} className="border-b border-hairline">
                  <td className="py-1 pr-4">{c.a.replace(/_/g, " ")} and {c.b.replace(/_/g, " ")}</td>
                  <td className="pr-4 font-mono">{c.target.toFixed(2)}</td>
                  <td className="pr-4 font-mono">{c.realized.toFixed(2)}</td>
                  <td className="font-mono">{c.abs_diff.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
      <Panel title="Diversity and duplicates">
        <dl className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
          <div><dt className="text-xs text-muted-foreground">Exact duplicate attribute sets</dt><dd className="font-medium">{d.exact_duplicate_attribute_sets}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Near-duplicate bio pairs</dt><dd className="font-medium">{d.near_duplicate_bios ?? "not compared"}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Unique bios</dt><dd className="font-medium">{d.unique_bios} of {d.size}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Bio word variety (distinct-1 / 2)</dt><dd className="font-medium">{d.bio_distinct_1 ? d.bio_distinct_1.toFixed(2) : "n/a"} / {d.bio_distinct_2 ? d.bio_distinct_2.toFixed(2) : "n/a"}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Rule-satisfaction failures</dt><dd className="font-medium">{d.unsatisfied_rules}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Model bios replaced by template</dt><dd className="font-medium">{d.llm_fallbacks}</dd></div>
        </dl>
        {Object.keys(d.rule_rejections).length > 0 && (
          <p className="mt-3 text-xs text-muted-foreground">
            Rejection sampling discarded draws that broke consistency rules:{" "}
            {Object.entries(d.rule_rejections).map(([k, v]) => `${k.replace(/_/g, " ")} (${v})`).join(", ")}.
          </p>
        )}
        <ul className="mt-3 list-disc pl-5 text-xs text-muted-foreground">
          {d.notes.map((n) => (<li key={n}>{n}</li>))}
        </ul>
      </Panel>
    </div>
  );
}

function PersonaTable({ versionId, status }: { versionId: number; status: string }) {
  const [offset, setOffset] = useState(0);
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const { data, error, loading } = useApi(() => popApi.personas(versionId, offset, query), [versionId, offset, query, status]);
  useEffect(() => {
    const t = setTimeout(() => {
      setQuery(q);
      setOffset(0);
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  if (error) return <ApiError error={error} />;
  const total = data?.total ?? 0;
  return (
    <Panel title="Personas">
      <label className="mb-3 flex max-w-sm flex-col gap-1 text-sm">
        Search name, id or biography
        <Input value={q} onChange={(e) => setQ(e.target.value)} />
      </label>
      {loading && !data ? <Loading what="personas" /> : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Personas in this population</caption>
            <thead>
              <tr className="border-b border-hairline">
                {["ID", "Name", "Age", "Region", "Employment", "Income", ""].map((h) => (
                  <th key={h} scope="col" className="py-1 pr-4">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data?.items.map((p: Persona) => (
                <PersonaRow key={p.synthetic_id} p={p} open={open === p.synthetic_id} toggle={() => setOpen(open === p.synthetic_id ? null : p.synthetic_id)} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="mt-3 flex items-center gap-3 text-sm">
        <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>Previous</Button>
        <span role="status">{total === 0 ? "No personas match" : `${offset + 1} to ${Math.min(offset + 25, total)} of ${total}`}</span>
        <Button variant="outline" size="sm" disabled={offset + 25 >= total} onClick={() => setOffset(offset + 25)}>Next</Button>
      </div>
    </Panel>
  );
}

function PersonaRow({ p, open, toggle }: { p: Persona; open: boolean; toggle: () => void }) {
  const a = p.attributes;
  return (
    <>
      <tr className="border-b border-hairline">
        <td className="py-1 pr-4 font-mono text-xs">{p.synthetic_id}</td>
        <td className="pr-4">{p.name}</td>
        <td className="pr-4">{String(a.age)}</td>
        <td className="pr-4">{String(a.region)}</td>
        <td className="pr-4">{String(a.employment).replace(/_/g, " ")}</td>
        <td className="pr-4">{String(a.income_band).replace(/_/g, " ")}</td>
        <td>
          <Button variant="ghost" size="xs" aria-expanded={open} onClick={toggle}>
            {open ? "Hide" : "Details"}
          </Button>
        </td>
      </tr>
      {open && (
        <tr className="border-b border-hairline bg-muted">
          <td colSpan={7} className="p-3 text-sm">
            <p className="mb-2">{p.bio}</p>
            {p.interests.length > 0 && <p className="text-xs text-muted-foreground">Interests: {p.interests.join(", ")}</p>}
            {p.brand_attitudes && <p className="text-xs text-muted-foreground">Brands: {p.brand_attitudes}</p>}
            {p.quirk && <p className="text-xs text-muted-foreground">Quirk: {p.quirk}</p>}
            <p className="mt-2 font-mono text-xs text-muted-foreground">
              {Object.entries(a).map(([k, v]) => `${k}=${String(v)}`).join("  ")}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">Bio source: {String(p.meta.enrichment ?? "unknown")}</p>
          </td>
        </tr>
      )}
    </>
  );
}

export function PopulationDetail({ versionId }: { versionId: number }) {
  const [tick, setTick] = useState(0);
  const { data, error, loading, reload } = useApi(() => popApi.detail(versionId), [versionId, tick]);
  const status = data?.version.status;
  useEffect(() => {
    if (status !== "generating") return;
    const t = setInterval(() => setTick((n) => n + 1), 2000);
    return () => clearInterval(t);
  }, [status]);

  if (loading && !data) return <Loading what="population" />;
  if (error || !data) return <ApiError error={error ?? "No data"} onRetry={reload} />;
  const v = data.version;
  const pct = v.progress_total > 0 ? Math.round((v.progress_done / v.progress_total) * 100) : null;
  return (
    <div className="flex flex-col gap-6">
      <Alert role="note">
        <AlertTitle>Synthetic people</AlertTitle>
        <AlertDescription>
          These personas are generated, not real. The distribution is an assumption, not a
          representative sample of any population.
        </AlertDescription>
      </Alert>
      <Panel title={`${v.name} v${v.version}`}>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <Badge variant={v.status === "ready" ? "secondary" : v.status === "failed" ? "destructive" : "default"} data-testid="pop-status">
            {v.status}
          </Badge>
          <span>{v.size} personas</span>
          <span className="text-muted-foreground">seed {v.seed} - {v.source}</span>
          {v.status === "ready" && (
            <span className="ml-auto flex gap-2">
              <a className={buttonVariants({ variant: "outline", size: "sm" })} href={popApi.exportUrl(v.id, "jsonl")} download>Export JSONL</a>
              <a className={buttonVariants({ variant: "outline", size: "sm" })} href={popApi.exportUrl(v.id, "csv")} download>Export CSV</a>
            </span>
          )}
        </div>
        {v.status === "generating" && (
          <div className="mt-3">
            <p className="text-sm" role="status">Writing biographies: {v.progress_done} of {v.progress_total}</p>
            <div role="progressbar" aria-label="Biographies written" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct ?? undefined} className="mt-1 h-3 overflow-hidden rounded-full border border-hairline bg-muted neu-inset">
              <div className="h-full rounded-full bg-primary" style={{ width: `${pct ?? 0}%` }} />
            </div>
          </div>
        )}
        {v.error && <p className="mt-3 text-sm text-destructive">{v.error}</p>}
      </Panel>
      {data.diagnostics && <DiagnosticsView d={data.diagnostics} />}
      {v.status !== "failed" && <PersonaTable versionId={v.id} status={v.status} />}
    </div>
  );
}
