import { EmptyState } from "@/components/shell/empty-state";
import { PageHeader } from "@/components/shell/page-header";

export default function Page() {
  return (
    <>
      <PageHeader
        title="Inference Lab"
        description="Detect your hardware, benchmark local runtimes and models, and get transparent recommendations."
        phase={4}
      />
      <EmptyState title="Not available yet">
        This section is not built yet. It is planned for phase 4.
      </EmptyState>
    </>
  );
}
