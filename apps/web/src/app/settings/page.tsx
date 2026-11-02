import { EmptyState } from "@/components/shell/empty-state";
import { PageHeader } from "@/components/shell/page-header";

export default function Page() {
  return (
    <>
      <PageHeader
        title="Settings"
        description="Configuration for this local install."
        phase={2}
      />
      <EmptyState title="Not available yet">
        This section is not built yet. It is planned for phase 2.
      </EmptyState>
    </>
  );
}
