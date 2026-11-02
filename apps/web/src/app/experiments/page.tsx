import { EmptyState } from "@/components/shell/empty-state";
import { PageHeader } from "@/components/shell/page-header";

export default function Page() {
  return (
    <>
      <PageHeader
        title="Experiments"
        description="Design product, advertising and pricing experiments."
        phase={7}
      />
      <EmptyState title="Not available yet">
        This section is not built yet. It is planned for phase 7.
      </EmptyState>
    </>
  );
}
