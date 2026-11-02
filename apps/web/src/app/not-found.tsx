import Link from "next/link";
import { EmptyState } from "@/components/shell/empty-state";
import { PageHeader } from "@/components/shell/page-header";
import { buttonVariants } from "@/components/ui/button";

export default function NotFound() {
  return (
    <>
      <PageHeader title="Page not found" description="That address does not exist in Simulacra." />
      <EmptyState title="Nothing here">
        <Link href="/" className={buttonVariants({ variant: "outline" })}>
          Back to dashboard
        </Link>
      </EmptyState>
    </>
  );
}
