"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { HistoryList } from "@/components/lab/history-list";
import { RunDetailView } from "@/components/lab/run-detail";
import { PageHeader } from "@/components/shell/page-header";
import { buttonVariants } from "@/components/ui/button";

function Inner() {
  const params = useSearchParams();
  const raw = params.get("id");
  const id = raw && /^\d+$/.test(raw) ? Number(raw) : null;
  if (id === null) return <HistoryList />;
  return (
    <>
      <Link href="/lab/history/" className={`${buttonVariants({ variant: "outline", size: "sm" })} mb-4`}>
        All benchmarks
      </Link>
      <RunDetailView runId={id} />
    </>
  );
}

export default function HistoryPage() {
  return (
    <>
      <PageHeader title="Benchmark history" description="Every benchmark you have run, with the raw evidence behind each number." />
      <Suspense fallback={<p role="status">Loading...</p>}>
        <Inner />
      </Suspense>
    </>
  );
}
