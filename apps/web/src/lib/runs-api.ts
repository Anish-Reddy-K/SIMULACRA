export type Run = {
  id: number;
  kind: string;
  name: string;
  state: string;
  total_units: number;
  done_units: number;
  error_units: number;
  batches_total: number;
  batches_failed: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  elapsed_s: number | null;
  rate_per_min: number | null;
  eta_s: number | null;
  error: string | null;
};

export const TERMINAL_STATES = ["completed", "completed_with_errors", "failed", "cancelled"];

export type RunAction = "pause" | "resume" | "cancel";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/v1/runs${path}`, init);
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // keep status
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const runsApi = {
  list: () => request<Run[]>(""),
  get: (id: number) => request<Run>(`/${id}`),
  act: (id: number, action: RunAction) => request<Run>(`/${id}/${action}`, { method: "POST" }),
};

/** Which controls make sense in each state (the server still validates). */
export function availableActions(state: string): RunAction[] {
  switch (state) {
    case "queued":
    case "running":
      return ["pause", "cancel"];
    case "paused":
      return ["resume", "cancel"];
    case "pausing":
      return ["resume", "cancel"];
    default:
      return [];
  }
}

export function stateLabel(state: string): string {
  return state.replace(/_/g, " ");
}

/** ETA is shown only when the server provides it; otherwise the UI is honestly indeterminate. */
export function describeEta(run: Run): string {
  if (TERMINAL_STATES.includes(run.state)) return "finished";
  if (run.state === "paused") return "paused";
  if (run.eta_s === null || run.rate_per_min === null) return "estimating...";
  const m = Math.round(run.eta_s / 60);
  return m < 1 ? "under a minute" : m < 90 ? `about ${m} min` : `about ${(run.eta_s / 3600).toFixed(1)} h`;
}
