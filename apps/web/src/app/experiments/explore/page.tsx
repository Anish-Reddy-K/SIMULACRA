"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { QueryPanel, SynthesisPanel, ThemesPanel } from "@/components/experiments/insights";
import { Loading } from "@/components/lab/ui";
import { PageHeader } from "@/components/shell/page-header";
import { buttonVariants } from "@/components/ui/button";
import { expApi, type TrialDetail } from "@/lib/exp-api";
import { useApi } from "@/lib/use-api";

function TrialDrawer({ id, onClose }: { id: number; onClose: () => void }) {
  const { data, error, loading } = useApi<TrialDetail>(() => expApi.trial(id), [id]);
  return (
    <aside aria-label={`Source trial ${id}`} className="rounded-lg border border-primary bg-card p-4 text-xs neu-raised-sm">
      <div className="mb-2 flex items-center justify-between">
        <p className="font-semibold">Source trial #{id}</p>
        <button type="button" className="underline" onClick={onClose}>Close</button>
      </div>
      {loading ? <Loading what="trial" /> : error || !data ? <p role="alert">{error}</p> : (
        <>
          <p>persona {data.persona_id}, status {data.status}, {Math.round(data.latency_ms)} ms</p>
          <p className="mt-2 font-semibold">Prompt sent to the model</p>
          <pre className="whitespace-pre-wrap font-mono">{data.prompt_text}</pre>
          <p className="mt-2 font-semibold">Raw model output</p>
          <pre className="whitespace-pre-wrap font-mono">{data.raw_output}</pre>
        </>
      )}
    </aside>
  );
}

function Inner() {
  const raw = useSearchParams().get("run");
  const id = raw && /^\d+$/.test(raw) ? Number(raw) : null;
  const [open, setOpen] = useState<number | null>(null);
  const results = useApi(() => (id === null ? Promise.reject(new Error("No run selected")) : expApi.results(id)), [id]);
  if (id === null) return <p role="alert">No run selected.</p>;
  const treatments = (results.data?.treatments ?? []).map((t) => ({ idx: t.idx, label: t.label }));
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap gap-2">
        <Link href={`/experiments/results/?run=${id}`} className={buttonVariants({ variant: "outline", size: "sm" })}>Back to results</Link>
        <a href={expApi.trialsCsvUrl(id)} download className={buttonVariants({ variant: "outline", size: "sm" })}>Export trials (CSV)</a>
      </div>
      {open !== null && <TrialDrawer id={open} onClose={() => setOpen(null)} />}
      <SynthesisPanel runId={id} onOpenTrial={setOpen} />
      <ThemesPanel runId={id} onOpenTrial={setOpen} />
      <QueryPanel runId={id} treatments={treatments} onOpenTrial={setOpen} />
    </div>
  );
}

export default function Explore() {
  return (
    <>
      <PageHeader title="Explore results" description="Evidence-linked findings, themes in the free text, and structured questions answered from the stored trials." />
      <Suspense fallback={<p role="status">Loading...</p>}><Inner /></Suspense>
    </>
  );
}
