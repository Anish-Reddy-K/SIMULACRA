import Link from "next/link";
import { HardwarePanel } from "@/components/lab/hardware-panel";
import { Recommendations } from "@/components/lab/recommendations";
import { RuntimesPanel } from "@/components/lab/runtimes-panel";
import { Section } from "@/components/lab/ui";
import { PageHeader } from "@/components/shell/page-header";
import { buttonVariants } from "@/components/ui/button";

export default function InferenceLab() {
  return (
    <>
      <PageHeader
        title="Inference Lab"
        description="Find the best local model and runtime for this machine. Every recommendation comes from benchmarks you ran here, with the evidence one click away."
      />
      <div className="mb-8 flex flex-wrap gap-3">
        <Link href="/lab/benchmark/" className={buttonVariants()}>
          Run a benchmark
        </Link>
        <Link href="/lab/history/" className={buttonVariants({ variant: "outline" })}>
          Benchmark history
        </Link>
      </div>
      <Section title="Hardware" id="hardware">
        <HardwarePanel />
      </Section>
      <Section title="Runtimes and models" id="runtimes">
        <RuntimesPanel />
      </Section>
      <Section title="Recommendations" id="recommendations">
        <Recommendations />
      </Section>
    </>
  );
}
