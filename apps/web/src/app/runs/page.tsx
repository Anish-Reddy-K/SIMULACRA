import { EmptyState } from "@/components/shell/empty-state";
import { PageHeader } from "@/components/shell/page-header";

export default function Page() {
  return (
    <>
      <PageHeader
        title="Runs"
        description="Monitor long-running simulations live and resume them after interruptions."
        phase={6}
      />
      <EmptyState title="Not available yet">
        This section is not built yet. It is planned for phase 6.
      </EmptyState>
    </>
  );
}
