"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { describeHealth, fetchHealth, type Health } from "@/lib/health";

export function ApiStatus() {
  const [health, setHealth] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then(setHealth)
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => controller.abort();
  }, []);

  const view = describeHealth(health, failed);
  return (
    <Badge variant={view.ok ? "secondary" : "warning"} role="status" data-testid="api-status">
      {view.label}
    </Badge>
  );
}
