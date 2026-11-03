import { RunList } from "@/components/runs/list";
import { PageHeader } from "@/components/shell/page-header";

export default function Runs() {
  return (
    <>
      <PageHeader
        title="Runs"
        description="Monitor long-running simulations live. Runs continue in the background when you close the browser and resume after interruptions."
      />
      <RunList />
    </>
  );
}
