"use client";

import Link from "next/link";
import { ApiError, Loading, Panel } from "@/components/lab/ui";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { labApi } from "@/lib/lab-api";
import { useApi } from "@/lib/use-api";

export function HistoryList() {
  const { data, error, loading, reload } = useApi(labApi.runs);
  if (loading) return <Loading what="history" />;
  if (error || !data) return <ApiError error={error ?? "No data"} onRetry={reload} />;
  if (data.length === 0) {
    return (
      <Panel as="h2" title="No benchmarks yet">
        <p className="text-sm text-muted-foreground">
          Results appear here after you run a benchmark.{" "}
          <Link href="/lab/benchmark/" className={buttonVariants({ variant: "link", size: "sm" })}>
            Run one now
          </Link>
        </p>
      </Panel>
    );
  }
  return (
    <Panel as="h2" title="Past benchmarks">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Benchmark history, newest first</caption>
          <thead>
            <tr className="border-b border-hairline">
              {["Run", "Started", "Stage", "Status", "Targets", ""].map((h) => (
                <th key={h} scope="col" className="py-2 pr-4">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((r) => (
              <tr key={r.id} className="border-b border-hairline">
                <td className="py-2 pr-4 font-mono">#{r.id}</td>
                <td className="pr-4">{new Date(r.created_at).toLocaleString()}</td>
                <td className="pr-4">{r.stage}</td>
                <td className="pr-4">
                  <Badge variant={r.status === "completed" ? "secondary" : r.status === "running" ? "default" : "warning"}>
                    {r.status.replace(/_/g, " ")}
                  </Badge>
                </td>
                <td className="pr-4 font-mono text-xs">{r.targets.map((t) => t.model).join(", ")}</td>
                <td>
                  <Link
                    href={r.status === "running" ? `/lab/benchmark/?id=${r.id}` : `/lab/history/?id=${r.id}`}
                    className={buttonVariants({ variant: "outline", size: "sm" })}
                  >
                    {r.status === "running" ? "Watch" : "Open"}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
