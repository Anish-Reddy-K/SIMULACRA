export type Health = {
  status: "ok" | "degraded";
  version: string;
  database: { ok: boolean; journal_mode: string | null };
  worker: { status: string };
};

export type HealthView = { label: string; ok: boolean };

export function describeHealth(health: Health | null, failed: boolean): HealthView {
  if (failed) return { label: "API unreachable", ok: false };
  if (!health) return { label: "Checking API...", ok: false };
  if (health.status !== "ok") return { label: "API degraded: database check failed", ok: false };
  return { label: `API ok (v${health.version})`, ok: true };
}

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const res = await fetch("/api/v1/health", { signal });
  if (!res.ok) throw new Error(`health request failed: ${res.status}`);
  return (await res.json()) as Health;
}
