import { PageHeader } from "@/components/shell/page-header";
import { EmptyState } from "@/components/shell/empty-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export default function Dashboard() {
  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Run simulated experiments with persistent AI personas on your own hardware."
      />
      <div className="grid gap-6 md:grid-cols-2">
        <EmptyState title="No experiments yet">
          Experiments appear here once you create one. The experiment builder arrives in a later
          phase.
        </EmptyState>
        <EmptyState title="Inference setup not benchmarked">
          The Inference Lab will measure which local model and runtime run best on this machine.
          Until then, nothing is recommended.
        </EmptyState>
      </div>
      <Alert className="mt-6">
        <AlertTitle>What results mean</AlertTitle>
        <AlertDescription>
          Results are simulated opinions from model-generated personas. They are not observed human
          behavior and not validated predictions.
        </AlertDescription>
      </Alert>
    </>
  );
}
