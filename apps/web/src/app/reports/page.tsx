"use client";

import Link from "next/link";
import { ApiError, Loading, Panel } from "@/components/lab/ui";
import { PageHeader } from "@/components/shell/page-header";
import { buttonVariants } from "@/components/ui/button";
import { expApi } from "@/lib/exp-api";
import { useApi } from "@/lib/use-api";

export default function Reports() {
  const { data, error, loading, reload } = useApi(expApi.reports);
  return (
    <>
      <PageHeader title="Reports" description="Evidence-linked results from completed experiments." />
      {loading ? <Loading what="reports" /> : error || !data ? <ApiError error={error ?? "No data"} onRetry={reload} /> : data.length === 0 ? (
        <Panel title="No reports yet"><p className="text-sm text-muted-foreground">Create a report from the results of a completed run.</p></Panel>
      ) : (
        <Panel title="Reports">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Reports, newest first</caption>
            <thead><tr className="border-b border-hairline">{["Report", "Run", "Created", ""].map((h) => (<th key={h} scope="col" className="py-1 pr-4">{h}</th>))}</tr></thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.id} className="border-b border-hairline">
                  <td className="py-2 pr-4 font-medium">{r.title}</td>
                  <td className="pr-4 font-mono">#{r.run_id}</td>
                  <td className="pr-4">{new Date(r.created_at).toLocaleString()}</td>
                  <td><Link href={`/reports/view/?id=${r.id}`} className={buttonVariants({ variant: "outline", size: "sm" })}>Open</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </>
  );
}
