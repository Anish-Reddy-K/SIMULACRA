"use client";

import Link from "next/link";
import { ApiError, Loading, Panel } from "@/components/lab/ui";
import { PageHeader } from "@/components/shell/page-header";
import { buttonVariants } from "@/components/ui/button";
import { expApi } from "@/lib/exp-api";
import { useApi } from "@/lib/use-api";

export default function Experiments() {
  const { data, error, loading, reload } = useApi(expApi.list);
  return (
    <>
      <PageHeader title="Experiments" description="Design product concept tests and compare how simulated people respond." />
      <div className="mb-6">
        <Link href="/experiments/new/" className={buttonVariants()}>New experiment</Link>
      </div>
      {loading ? <Loading what="experiments" /> : error || !data ? <ApiError error={error ?? "No data"} onRetry={reload} /> : data.length === 0 ? (
        <Panel title="No experiments yet"><p className="text-sm text-muted-foreground">Create your first experiment to get started.</p></Panel>
      ) : (
        <Panel title="Your experiments">
          <ul className="flex flex-col gap-2 text-sm">
            {data.map((e) => (
              <li key={e.id} className="flex flex-wrap items-baseline justify-between gap-2 border-b border-hairline pb-2">
                <span><span className="font-medium">{e.name}</span> <span className="text-muted-foreground">{e.research_question}</span></span>
                <span className="text-xs text-muted-foreground">{e.treatments.map((t) => t.label).join(", ")}</span>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </>
  );
}
