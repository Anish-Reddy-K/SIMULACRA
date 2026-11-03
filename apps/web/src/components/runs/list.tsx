"use client";

import Link from "next/link";
import { ApiError, Loading, Panel } from "@/components/lab/ui";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { runsApi, stateLabel, TERMINAL_STATES } from "@/lib/runs-api";
import { useApi } from "@/lib/use-api";

export function RunList() {
  const { data, error, loading, reload } = useApi(runsApi.list);
  if (loading) return <Loading what="runs" />;
  if (error || !data) return <ApiError error={error ?? "No data"} onRetry={reload} />;
  if (data.length === 0) {
    return (
      <Panel title="No runs yet">
        <p className="text-sm text-muted-foreground">
          Runs appear here once you start an experiment. They keep running in the background even if you
          close this page.
        </p>
      </Panel>
    );
  }
  return (
    <Panel title="Runs">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Runs, newest first</caption>
          <thead>
            <tr className="border-b border-hairline">
              {["Run", "Name", "State", "Progress", ""].map((h) => (
                <th key={h} scope="col" className="py-2 pr-4">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((r) => (
              <tr key={r.id} className="border-b border-hairline">
                <td className="py-2 pr-4 font-mono">#{r.id}</td>
                <td className="pr-4">{r.name}</td>
                <td className="pr-4">
                  <Badge variant={r.state === "completed" ? "secondary" : TERMINAL_STATES.includes(r.state) ? "warning" : "default"}>
                    {stateLabel(r.state)}
                  </Badge>
                </td>
                <td className="pr-4">{r.done_units} / {r.total_units}</td>
                <td>
                  <Link href={`/runs/view/?id=${r.id}`} className={buttonVariants({ variant: "outline", size: "sm" })}>
                    {TERMINAL_STATES.includes(r.state) ? "Open" : "Watch"}
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
