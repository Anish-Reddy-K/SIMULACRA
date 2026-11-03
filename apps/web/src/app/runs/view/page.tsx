"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { RunMonitor } from "@/components/runs/monitor";
import { PageHeader } from "@/components/shell/page-header";
import { buttonVariants } from "@/components/ui/button";

function Inner() {
  const raw = useSearchParams().get("id");
  const id = raw && /^\d+$/.test(raw) ? Number(raw) : null;
  if (id === null) return <p role="alert">No run selected.</p>;
  return <RunMonitor runId={id} />;
}

export default function View() {
  return (
    <>
      <PageHeader title="Run monitor" description="Live status of one run." />
      <Link href="/runs/" className={`${buttonVariants({ variant: "outline", size: "sm" })} mb-4`}>
        All runs
      </Link>
      <Suspense fallback={<p role="status">Loading...</p>}>
        <Inner />
      </Suspense>
    </>
  );
}
