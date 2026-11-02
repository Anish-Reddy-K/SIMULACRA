import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-2">
        <h2 className="text-base font-semibold">{title}</h2>
        <div className="max-w-prose text-sm text-muted-foreground">{children}</div>
      </CardContent>
    </Card>
  );
}
