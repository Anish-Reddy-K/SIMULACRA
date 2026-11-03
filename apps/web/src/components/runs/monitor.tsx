"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ApiError, Fact, Loading, Panel } from "@/components/lab/ui";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { formatDuration, formatNumber } from "@/lib/format";
import {
  availableActions,
  describeEta,
  runsApi,
  stateLabel,
  TERMINAL_STATES,
  type Run,
  type RunAction,
} from "@/lib/runs-api";

const ACTION_LABEL: Record<RunAction, string> = { pause: "Pause", resume: "Resume", cancel: "Cancel run" };

function stateVariant(state: string): "default" | "secondary" | "warning" | "destructive" {
  if (state === "completed") return "secondary";
  if (state === "failed" || state === "cancelled") return "destructive";
  if (state === "completed_with_errors" || state === "paused" || state === "pausing") return "warning";
  return "default";
}

export function RunMonitor({ runId }: { runId: number }) {
  const [run, setRun] = useState<Run | null>(null);
  const [events, setEvents] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [connected, setConnected] = useState(true);

  useEffect(() => {
    runsApi.get(runId).then(setRun).catch((e: unknown) => setError(e instanceof Error ? e.message : "Request failed"));
    const es = new EventSource(`/api/v1/runs/${runId}/events`);
    const addEvent = (e: Event) => {
      const message = JSON.parse((e as MessageEvent<string>).data) as string;
      setEvents((prev) => [...prev, message].slice(-200));
    };
    es.addEventListener("state", addEvent);
    es.addEventListener("retry", addEvent);
    es.addEventListener("error", (e) => {
      if ((e as MessageEvent<string>).data) addEvent(e);
    });
    es.addEventListener("progress", (e) => {
      setConnected(true);
      const snap = JSON.parse((e as MessageEvent<string>).data) as Run;
      setRun(snap);
      if (TERMINAL_STATES.includes(snap.state)) es.close();
    });
    es.onerror = () => setConnected(false); // the browser reconnects and resumes from Last-Event-ID
    es.onopen = () => setConnected(true);
    return () => es.close();
  }, [runId]);

  const act = useCallback(
    async (action: RunAction) => {
      setActionError(null);
      try {
        setRun(await runsApi.act(runId, action));
      } catch (e) {
        setActionError(e instanceof Error ? e.message : "Action failed");
      }
    },
    [runId],
  );

  if (error) return <ApiError error={error} />;
  if (!run) return <Loading what="run" />;
  const terminal = TERMINAL_STATES.includes(run.state);
  const pct = run.total_units > 0 ? Math.round((run.done_units / run.total_units) * 100) : 0;

  return (
    <div className="flex flex-col gap-6">
      {!connected && !terminal && (
        <Alert variant="warning" role="status">
          <AlertTitle>Reconnecting</AlertTitle>
          <AlertDescription>
            Lost the live connection. The run keeps going in the background and this page will catch up
            when it reconnects.
          </AlertDescription>
        </Alert>
      )}
      <Panel as="h2" title={`${run.name} (#${run.id})`}>
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant={stateVariant(run.state)} data-testid="run-state">
            {stateLabel(run.state)}
          </Badge>
          <span className="text-sm text-muted-foreground">Runs continue when the browser is closed.</span>
          <span className="ml-auto flex gap-2">
            {run.kind === "experiment" && run.done_units > 0 && (
              <Link href={`/experiments/results/?run=${run.id}`} className={buttonVariants({ variant: "default", size: "sm" })}>
                View results
              </Link>
            )}
            {availableActions(run.state).map((a) => (
              <Button key={a} variant={a === "cancel" ? "destructive" : "outline"} size="sm" onClick={() => void act(a)}>
                {ACTION_LABEL[a]}
              </Button>
            ))}
          </span>
        </div>
        {actionError && (
          <p role="alert" className="mt-2 text-sm text-destructive">
            {actionError}
          </p>
        )}
        <div className="mt-4">
          <p className="text-sm" data-testid="run-progress-text">
            {run.done_units} of {run.total_units} units complete ({pct}%)
          </p>
          <div
            role="progressbar"
            aria-label="Units completed"
            aria-valuemin={0}
            aria-valuemax={run.total_units}
            aria-valuenow={run.done_units}
            className="mt-2 h-3 overflow-hidden rounded-full border border-hairline bg-muted neu-inset"
          >
            <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
          </div>
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
          <Fact label="Elapsed" value={run.elapsed_s === null ? "not started" : formatDuration(run.elapsed_s)} />
          <Fact label="Rate" value={run.rate_per_min !== null ? `${formatNumber(run.rate_per_min, 1)} units/min` : terminal ? "not applicable" : "measuring..."} />
          <Fact label="Time remaining" value={describeEta(run)} />
          <Fact label="Errors" value={`${run.error_units} units, ${run.batches_failed} batches`} warn={run.error_units > 0 || run.batches_failed > 0} />
        </dl>
        <p className="mt-3 text-xs text-muted-foreground">
          The estimate appears only once enough units have completed to measure a reliable rate.
          Pausing waits for the batches already in progress to finish.
        </p>
        {run.error && <p className="mt-2 text-sm text-destructive">{run.error}</p>}
      </Panel>
      <Panel as="h2" title="Activity">
        <ul aria-live="polite" className="flex max-h-72 flex-col gap-1 overflow-auto rounded-lg border border-hairline bg-muted p-3 font-mono text-xs neu-inset">
          {events.length === 0 ? <li>No events yet.</li> : events.map((m, i) => <li key={`${i}-${m}`}>{m}</li>)}
        </ul>
      </Panel>
    </div>
  );
}
