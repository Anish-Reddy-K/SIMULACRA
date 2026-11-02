"use client";

import { useEffect, useState } from "react";
import { describeHealth, fetchHealth, type Health } from "@/lib/health";

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then(setHealth)
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          console.error(err);
          setFailed(true);
        }
      });
    return () => controller.abort();
  }, []);

  const view = describeHealth(health, failed);

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-4 px-6 py-16">
      <h1 className="text-3xl font-semibold tracking-tight">Simulacra</h1>
      <p className="text-zinc-600">
        Local synthetic-population experiments. Simulated opinions are not human predictions.
      </p>
      <p role="status" data-testid="api-status" className={view.ok ? "text-emerald-700" : "text-amber-700"}>
        {view.label}
      </p>
    </main>
  );
}
