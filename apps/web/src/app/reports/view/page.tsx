"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { ReportView } from "@/components/experiments/report-view";
import { PageHeader } from "@/components/shell/page-header";
import { buttonVariants } from "@/components/ui/button";

function Inner() {
  const raw = useSearchParams().get("id");
  const id = raw && /^\d+$/.test(raw) ? Number(raw) : null;
  if (id === null) return <p role="alert">No report selected.</p>;
  return <ReportView id={id} />;
}

export default function View() {
  return (
    <>
      <PageHeader title="Report" description="Evidence-linked findings with full reproducibility metadata." />
      <Link href="/reports/" className={`${buttonVariants({ variant: "outline", size: "sm" })} mb-4`}>All reports</Link>
      <Suspense fallback={<p role="status">Loading...</p>}><Inner /></Suspense>
    </>
  );
}
