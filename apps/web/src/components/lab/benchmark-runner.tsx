"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, Loading, Panel } from "@/components/lab/ui";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { labApi, type RunSummary } from "@/lib/lab-api";
import { formatDuration } from "@/lib/format";
import { useApi } from "@/lib/use-api";

const STAGES = [
  { id: "screen", label: "Compatibility check", detail: "Loads the model and checks structured output works. Seconds. Produces no performance numbers, so nothing can be recommended from it." },
  { id: "quick", label: "Quick benchmark", detail: "A compact representative workload at two concurrency levels. Results are indicative only." },
  { id: "detailed", label: "Detailed benchmark", detail: "Concurrency sweep, repeated runs, long contexts, a batch, strict JSON and the consistency suite. The most useful evidence." },
  { id: "soak", label: "Sustained run", detail: "Runs continuously for the duration you choose to look for slowdowns and failures." },
] as const;

type Candidate = { key: string; label: string; base_url: string; model: string; defaultMode: string };

const TERMINAL = ["completed", "completed_with_errors", "failed", "cancelled"];

function useCandidates() {
  const { data, error, loading, reload } = useApi(labApi.runtimes);
  const candidates: Candidate[] = (data?.runtimes ?? [])
    .filter((r) => r.running && r.info)
    .flatMap((r) =>
      r.models.map((m) => ({
        key: `${r.base_url}|${m.name}`,
        label: `${r.info?.kind} / ${m.name}`,
        base_url: r.base_url,
        model: m.name,
        defaultMode: r.info?.capabilities.json_schema === null ? "prompted" : "constrained",
      })),
    );
  return { candidates, error, loading, reload };
}

function Setup({ onStarted }: { onStarted: (run: RunSummary) => void }) {
  const { candidates, error, loading, reload } = useCandidates();
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [modes, setModes] = useState<Record<string, string>>({});
  const [stage, setStage] = useState<string>("quick");
  const [soakMinutes, setSoakMinutes] = useState("5");
  const [submitting, setSubmitting] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  if (loading) return <Loading what="available models" />;
  if (error) return <ApiError error={error} onRetry={reload} />;

  const chosen = candidates.filter((c) => selected[c.key]);

  async function start() {
    setSubmitting(true);
    setProblem(null);
    try {
      const run = await labApi.start({
        stage,
        soak_seconds: Math.max(10, Number(soakMinutes) * 60) || 300,
        targets: chosen.map((c) => ({
          base_url: c.base_url,
          model: c.model,
          structured_mode: modes[c.key] ?? c.defaultMode,
        })),
      });
      onStarted(run);
    } catch (e) {
      setProblem(e instanceof Error ? e.message : "Could not start the benchmark");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Panel as="h2" title="1. Choose what to test">
        {candidates.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No running runtime has any models. Start a runtime and pull a model first (see{" "}
            <Link className="underline" href="/lab/">
              Inference Lab
            </Link>
            ). Simulacra never downloads models for you.
          </p>
        ) : (
          <fieldset className="flex flex-col gap-3">
            <legend className="sr-only">Models to benchmark</legend>
            {candidates.map((c) => (
              <div key={c.key} className="flex flex-wrap items-center gap-3">
                <label className="flex min-h-11 items-center gap-3">
                  <input
                    type="checkbox"
                    className="size-5 accent-primary"
                    checked={!!selected[c.key]}
                    onChange={(e) => setSelected({ ...selected, [c.key]: e.target.checked })}
                  />
                  <span className="font-mono text-sm">{c.label}</span>
                </label>
                {selected[c.key] && c.label.startsWith("openai") && (
                  <label className="flex items-center gap-2 text-xs text-muted-foreground">
                    JSON output
                    <select
                      className="h-9 rounded-lg border border-input bg-card px-2 text-sm text-foreground"
                      value={modes[c.key] ?? c.defaultMode}
                      onChange={(e) => setModes({ ...modes, [c.key]: e.target.value })}
                    >
                      <option value="constrained">Server enforces schema</option>
                      <option value="prompted">Schema described in prompt</option>
                    </select>
                  </label>
                )}
              </div>
            ))}
            <p className="text-xs text-muted-foreground">
              For a fair comparison, run one runtime at a time on the same model file and stop other
              model servers first. Memory pressure from other servers changes the results.
            </p>
          </fieldset>
        )}
      </Panel>
      <Panel as="h2" title="2. Choose how thorough">
        <fieldset className="flex flex-col gap-3">
          <legend className="sr-only">Benchmark stage</legend>
          {STAGES.map((s) => (
            <label key={s.id} className="flex min-h-11 items-start gap-3">
              <input
                type="radio"
                name="stage"
                className="mt-1 size-5 accent-primary"
                checked={stage === s.id}
                onChange={() => setStage(s.id)}
              />
              <span>
                <span className="font-medium">{s.label}</span>
                <span className="block text-sm text-muted-foreground">{s.detail}</span>
              </span>
            </label>
          ))}
          {stage === "soak" && (
            <label className="flex items-center gap-3 text-sm">
              Duration (minutes)
              <Input
                type="number"
                min={1}
                max={1440}
                className="w-28"
                value={soakMinutes}
                onChange={(e) => setSoakMinutes(e.target.value)}
              />
            </label>
          )}
        </fieldset>
        <p className="mt-3 text-sm text-muted-foreground">
          You can skip benchmarking entirely. Simulacra will simply not recommend anything it has
          not measured. Duration depends on how fast your model is; live progress is shown below.
        </p>
      </Panel>
      {problem && (
        <Alert variant="destructive" role="alert">
          <AlertTitle>Could not start</AlertTitle>
          <AlertDescription>{problem}</AlertDescription>
        </Alert>
      )}
      <div>
        <Button onClick={start} disabled={chosen.length === 0 || submitting}>
          {submitting ? "Starting..." : `Start benchmark${chosen.length > 1 ? ` (${chosen.length} models)` : ""}`}
        </Button>
      </div>
    </div>
  );
}

function Progress({ runId }: { runId: number }) {
  const [run, setRun] = useState<RunSummary | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [now, setNow] = useState(() => Date.now());
  const [error, setError] = useState<string | null>(null);
  const source = useRef<EventSource | null>(null);

  const refresh = useCallback(() => {
    labApi
      .run(runId)
      .then((d) => {
        setRun(d.run);
        setLog(d.events);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Request failed"));
  }, [runId]);

  useEffect(() => {
    refresh();
    const es = new EventSource(`/api/v1/lab/benchmarks/${runId}/events`);
    source.current = es;
    es.addEventListener("log", (e) => {
      const message = JSON.parse((e as MessageEvent<string>).data) as string;
      setLog((prev) => (prev.some((l) => l.endsWith(message)) ? prev : [...prev, message]));
    });
    es.addEventListener("progress", (e) => {
      const p = JSON.parse((e as MessageEvent<string>).data) as {
        status: string;
        op: string | null;
        done: number;
        total: number;
      };
      setRun((prev) =>
        prev ? { ...prev, status: p.status, op: p.op, op_done: p.done, op_total: p.total } : prev,
      );
      if (TERMINAL.includes(p.status)) {
        es.close();
        refresh();
      }
    });
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      es.close();
      clearInterval(timer);
    };
  }, [runId, refresh]);

  if (error) return <ApiError error={error} />;
  if (!run) return <Loading what="benchmark" />;
  const finished = TERMINAL.includes(run.status);
  const started = new Date(run.created_at).getTime();
  const end = run.finished_at ? new Date(run.finished_at).getTime() : now;
  const pct = run.op_total > 0 ? Math.round((run.op_done / run.op_total) * 100) : null;

  return (
    <Panel as="h2" title={`Benchmark #${run.id} (${run.stage})`}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant={run.status === "failed" || run.status === "cancelled" ? "destructive" : finished ? "secondary" : "default"} data-testid="run-status">
            {run.status.replace(/_/g, " ")}
          </Badge>
          <span className="text-sm text-muted-foreground">
            Elapsed {formatDuration(Math.max(0, (end - started) / 1000))}
          </span>
          {!finished && (
            <Button variant="destructive" size="sm" onClick={() => void labApi.cancel(run.id).then(refresh)}>
              Cancel
            </Button>
          )}
        </div>
        {!finished && (
          <div>
            <p className="text-sm" data-testid="current-op">
              {run.op ?? "Starting..."}
              {run.op_total > 0 && ` - ${run.op_done} of ${run.op_total} in this step`}
            </p>
            <div
              role="progressbar"
              aria-label="Progress of the current step"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={pct ?? undefined}
              className="mt-2 h-3 overflow-hidden rounded-full border border-hairline bg-muted neu-inset"
            >
              <div
                className={pct === null ? "h-full w-1/3 animate-pulse rounded-full bg-primary" : "h-full rounded-full bg-primary"}
                style={pct === null ? undefined : { width: `${pct}%` }}
              />
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Progress is per step. The total number of steps can grow while the concurrency sweep
              runs, so no overall percentage is shown.
            </p>
          </div>
        )}
        {run.error && (
          <Alert variant="destructive" role="alert">
            <AlertTitle>Run failed</AlertTitle>
            <AlertDescription>{run.error}</AlertDescription>
          </Alert>
        )}
        <div>
          <h3 className="mb-1 text-sm font-semibold">Activity</h3>
          <ul aria-live="polite" className="flex max-h-60 flex-col gap-1 overflow-auto rounded-lg border border-hairline bg-muted p-3 font-mono text-xs neu-inset">
            {log.map((l, i) => (
              <li key={`${i}-${l}`}>{l}</li>
            ))}
          </ul>
        </div>
        {finished && (
          <div className="flex gap-3">
            <Link href={`/lab/history/?id=${run.id}`} className={buttonVariants()}>
              View results and evidence
            </Link>
            <Link href="/lab/" className={buttonVariants({ variant: "outline" })}>
              See recommendations
            </Link>
          </div>
        )}
      </div>
    </Panel>
  );
}

export function BenchmarkRunner({ runId }: { runId: number | null }) {
  const [started, setStarted] = useState<number | null>(null);
  const id = runId ?? started;
  if (id !== null) {
    return <Progress runId={id} />;
  }
  return (
    <Setup
      onStarted={(r) => {
        setStarted(r.id);
        window.history.replaceState(null, "", `/lab/benchmark/?id=${r.id}`);
      }}
    />
  );
}
