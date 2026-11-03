"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, Loading, Panel } from "@/components/lab/ui";
import { CreateForm, ImportForm } from "@/components/populations/create-form";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { popApi } from "@/lib/pop-api";
import { useApi } from "@/lib/use-api";

export function PopulationList() {
  const router = useRouter();
  const { data, error, loading, reload } = useApi(popApi.list);
  const open = (id: number) => router.push(`/populations/view/?id=${id}`);
  return (
    <div className="flex flex-col gap-6">
      <CreateForm onCreated={(v) => open(v.id)} />
      <ImportForm onCreated={(v) => open(v.id)} />
      {loading ? (
        <Loading what="populations" />
      ) : error || !data ? (
        <ApiError error={error ?? "No data"} onRetry={reload} />
      ) : (
        <Panel title="Your populations">
          {data.length === 0 ? (
            <p className="text-sm text-muted-foreground">No populations yet. Generate one above.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Populations, newest first</caption>
                <thead>
                  <tr className="border-b border-hairline">
                    {["Name", "Version", "Personas", "Source", "Status", ""].map((h) => (
                      <th key={h} scope="col" className="py-2 pr-4">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.map((v) => (
                    <tr key={v.id} className="border-b border-hairline">
                      <td className="py-2 pr-4 font-medium">{v.name}</td>
                      <td className="pr-4">v{v.version}</td>
                      <td className="pr-4">{v.size}</td>
                      <td className="pr-4">{v.source}</td>
                      <td className="pr-4">
                        <Badge variant={v.status === "ready" ? "secondary" : v.status === "failed" ? "destructive" : "default"}>
                          {v.status}
                          {v.status === "generating" && v.progress_total > 0 ? ` ${v.progress_done}/${v.progress_total}` : ""}
                        </Badge>
                      </td>
                      <td>
                        <Link href={`/populations/view/?id=${v.id}`} className={buttonVariants({ variant: "outline", size: "sm" })}>
                          Open
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      )}
    </div>
  );
}
