import { EmptyState } from "@/components/shell/empty-state";
import { PageHeader } from "@/components/shell/page-header";

export default function Page() {
  return (
    <>
      <PageHeader
        title="Populations"
        description="Generate and inspect versioned synthetic populations."
        phase={5}
      />
      <EmptyState title="Not available yet">
        This section is not built yet. It is planned for phase 5.
      </EmptyState>
    </>
  );
}
