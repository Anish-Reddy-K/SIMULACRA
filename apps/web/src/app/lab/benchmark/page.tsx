"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { BenchmarkRunner } from "@/components/lab/benchmark-runner";
import { PageHeader } from "@/components/shell/page-header";

function Inner() {
  const params = useSearchParams();
  const raw = params.get("id");
  const id = raw && /^\d+$/.test(raw) ? Number(raw) : null;
  return <BenchmarkRunner runId={id} />;
}

export default function BenchmarkPage() {
  return (
    <>
      <PageHeader
        title="Run a benchmark"
        description="Measure speed, memory, reliability and behavioral consistency for the models on this machine."
      />
      <Suspense fallback={<p role="status">Loading...</p>}>
        <Inner />
      </Suspense>
    </>
  );
}
