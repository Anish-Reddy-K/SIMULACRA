"use client";

import Link from "next/link";
import { ApiError, EvidenceBadge, Loading } from "@/components/lab/ui";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { labApi, type Recommendation } from "@/lib/lab-api";
import { formatNumber } from "@/lib/format";
import { useApi } from "@/lib/use-api";

function RecommendationCard({ rec }: { rec: Recommendation }) {
  const sel = rec.selected;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <h3 className="text-base font-semibold">{rec.title}</h3>
          {rec.provisional && <Badge variant="warning">Provisional</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        {sel ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm font-medium">{sel.label}</span>
              <EvidenceBadge level={sel.evidence} />
            </div>
            <p className="text-muted-foreground">
              {formatNumber(sel.valid_per_min, 1)} valid trials/min measured at concurrency{" "}
              {sel.best_concurrency}
            </p>
          </>
        ) : (
          <p className="text-muted-foreground">Nothing recommended yet.</p>
        )}
        <ul className="list-disc pl-5 text-muted-foreground">
          {rec.rationale.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        {rec.considered.length > 0 && (
          <details>
            <summary className="cursor-pointer font-medium">
              Other options considered ({rec.considered.length})
            </summary>
            <ul className="mt-2 flex flex-col gap-1">
              {rec.considered.map((c, i) => (
                <li key={`${c.label}-${i}`} className="text-xs">
                  <span className="font-mono">{c.label}</span>{" "}
                  <Badge variant="outline">{c.status.replace("_", " ")}</Badge>
                  <span className="text-muted-foreground"> {c.detail}</span>
                </li>
              ))}
            </ul>
          </details>
        )}
        <p className="text-xs text-muted-foreground">
          <strong>When another choice is better:</strong> {rec.when_different}
        </p>
        {rec.caveats.length > 0 && (
          <details>
            <summary className="cursor-pointer text-xs font-medium">Limitations</summary>
            <ul className="mt-1 list-disc pl-5 text-xs text-muted-foreground">
              {rec.caveats.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </details>
        )}
      </CardContent>
    </Card>
  );
}

export function Recommendations() {
  const { data, error, loading, reload } = useApi(labApi.recommendations);
  if (loading) return <Loading what="recommendations" />;
  if (error || !data) return <ApiError error={error ?? "No data"} onRetry={reload} />;
  const anySelected = data.some((r) => r.selected);
  return (
    <>
      {!anySelected && (
        <p className="mb-4 text-sm text-muted-foreground">
          Recommendations come only from measurements on this machine.{" "}
          <Link href="/lab/benchmark/" className={buttonVariants({ variant: "link", size: "sm" })}>
            Run a benchmark
          </Link>
        </p>
      )}
      <div className="grid gap-6 md:grid-cols-2">
        {data.map((r) => (
          <RecommendationCard key={r.goal} rec={r} />
        ))}
      </div>
    </>
  );
}
