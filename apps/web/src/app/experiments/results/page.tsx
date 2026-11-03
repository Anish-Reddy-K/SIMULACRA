"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { ResultsView } from "@/components/experiments/results-view";
import { PageHeader } from "@/components/shell/page-header";
import { buttonVariants } from "@/components/ui/button";

function Inner() {
  const raw = useSearchParams().get("run");
  const id = raw && /^\d+$/.test(raw) ? Number(raw) : null;
  if (id === null) return <p role="alert">No run selected.</p>;
  return (
    <>
      <Link href={`/runs/view/?id=${id}`} className={`${buttonVariants({ variant: "outline", size: "sm" })} mb-4`}>
        Back to run
      </Link>
      <ResultsView runId={id} />
    </>
  );
}

export default function Results() {
  return (
    <>
      <PageHeader title="Results" description="Findings from a completed run, computed from the stored trials." />
      <Suspense fallback={<p role="status">Loading...</p>}><Inner /></Suspense>
    </>
  );
}
