import type { ReactNode } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { EVIDENCE_LABEL } from "@/lib/format";

export function EvidenceBadge({ level }: { level: string }) {
  return (
    <Badge variant={level === "quick" || level === "screened" ? "warning" : "secondary"}>
      Evidence: {EVIDENCE_LABEL[level] ?? level}
    </Badge>
  );
}

export function Section({
  title,
  children,
  id,
  action,
}: {
  title: string;
  children: ReactNode;
  id?: string;
  action?: ReactNode;
}) {
  return (
    <section aria-labelledby={`${id ?? title}-h`} id={id} className="mb-8">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 id={`${id ?? title}-h`} className="text-xl font-semibold tracking-tight">
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Fact({ label, value, warn }: { label: string; value: ReactNode; warn?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={warn ? "font-medium text-warning" : "font-medium"}>{value}</dd>
    </div>
  );
}

export function Loading({ what }: { what: string }) {
  return (
    <p role="status" className="text-sm text-muted-foreground">
      Loading {what}...
    </p>
  );
}

export function ApiError({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <Alert variant="destructive" role="alert">
      <AlertTitle>Could not load this section</AlertTitle>
      <AlertDescription>
        {error}
        {onRetry && (
          <button type="button" className="ml-2 underline" onClick={onRetry}>
            Try again
          </button>
        )}
      </AlertDescription>
    </Alert>
  );
}

export function Panel({
  title,
  children,
  as: Heading = "h3",
}: {
  title: string;
  children: ReactNode;
  as?: "h2" | "h3";
}) {
  return (
    <Card>
      <CardHeader>
        <Heading className="text-base font-semibold">{title}</Heading>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export type BarRow = { label: string; value: number | null; text: string; note?: string };

/** Accessible bar chart: every bar carries its value as text, bars themselves are decorative. */
export function BarChart({ title, rows, hint }: { title: string; rows: BarRow[]; hint?: string }) {
  const max = Math.max(...rows.map((r) => r.value ?? 0), 0);
  return (
    <figure className="flex flex-col gap-2">
      <figcaption className="text-sm font-semibold">{title}</figcaption>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      <ul className="flex flex-col gap-2">
        {rows.map((r) => (
          <li key={r.label} className="flex flex-col gap-1">
            <div className="flex justify-between gap-3 text-sm">
              <span className="min-w-0 truncate">{r.label}</span>
              <span className="shrink-0 font-mono text-xs">{r.text}</span>
            </div>
            <div aria-hidden="true" className="h-3 rounded-full border border-hairline bg-muted neu-inset">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: max > 0 && r.value !== null ? `${(r.value / max) * 100}%` : "0%" }}
              />
            </div>
            {r.note && <span className="text-xs text-muted-foreground">{r.note}</span>}
          </li>
        ))}
      </ul>
    </figure>
  );
}
