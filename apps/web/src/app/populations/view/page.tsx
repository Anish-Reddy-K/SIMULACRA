"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { PopulationDetail } from "@/components/populations/detail";
import { PageHeader } from "@/components/shell/page-header";
import { buttonVariants } from "@/components/ui/button";

function Inner() {
  const raw = useSearchParams().get("id");
  const id = raw && /^\d+$/.test(raw) ? Number(raw) : null;
  if (id === null) return <p role="alert">No population selected.</p>;
  return <PopulationDetail versionId={id} />;
}

export default function View() {
  return (
    <>
      <PageHeader title="Population" description="Quality diagnostics and personas for one population version." />
      <Link href="/populations/" className={`${buttonVariants({ variant: "outline", size: "sm" })} mb-4`}>
        All populations
      </Link>
      <Suspense fallback={<p role="status">Loading...</p>}>
        <Inner />
      </Suspense>
    </>
  );
}
