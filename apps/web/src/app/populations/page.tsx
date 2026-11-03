import { PopulationList } from "@/components/populations/list";
import { PageHeader } from "@/components/shell/page-header";

export default function Populations() {
  return (
    <>
      <PageHeader
        title="Populations"
        description="Generate versioned synthetic populations from explicit assumptions, inspect their quality, and export them."
      />
      <PopulationList />
    </>
  );
}
