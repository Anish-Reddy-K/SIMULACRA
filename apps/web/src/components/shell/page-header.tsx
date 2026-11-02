import { Badge } from "@/components/ui/badge";

export function PageHeader({
  title,
  description,
  phase,
}: {
  title: string;
  description: string;
  phase?: number;
}) {
  return (
    <div className="mb-8 flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
        {phase !== undefined && <Badge variant="outline">Planned: phase {phase}</Badge>}
      </div>
      <p className="max-w-prose text-muted-foreground">{description}</p>
    </div>
  );
}
