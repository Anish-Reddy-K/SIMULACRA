import { Wizard } from "@/components/experiments/wizard";
import { PageHeader } from "@/components/shell/page-header";

export default function NewExperiment() {
  return (
    <>
      <PageHeader title="New experiment" description="Describe an idea, choose simulated people and a local model, and run a product concept test." />
      <Wizard />
    </>
  );
}
