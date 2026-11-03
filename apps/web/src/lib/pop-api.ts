export type PopVersion = {
  id: number;
  population_id: number;
  name: string;
  version: number;
  status: string;
  source: string;
  size: number;
  seed: number;
  created_at: string;
  progress_done: number;
  progress_total: number;
  error: string | null;
  enrichment: Record<string, unknown>;
};

export type MarginalCheck = {
  attribute: string;
  target: Record<string, number>;
  realized: Record<string, number>;
  max_abs_diff: number;
};

export type Diagnostics = {
  size: number;
  marginals: MarginalCheck[];
  max_marginal_diff: number;
  correlations: { a: string; b: string; target: number; realized: number; abs_diff: number }[];
  max_correlation_diff: number | null;
  exact_duplicate_attribute_sets: number;
  near_duplicate_bios: number | null;
  bio_distinct_1: number | null;
  bio_distinct_2: number | null;
  unique_bios: number;
  categorical_coverage: Record<string, number>;
  rule_rejections: Record<string, number>;
  unsatisfied_rules: number;
  llm_fallbacks: number;
  notes: string[];
};

export type VersionDetail = {
  version: PopVersion;
  spec: Record<string, unknown>;
  diagnostics: Diagnostics | null;
};

export type Persona = {
  synthetic_id: string;
  name: string;
  attributes: Record<string, string | number | boolean>;
  bio: string;
  interests: string[];
  brand_attitudes: string;
  quirk: string;
  meta: Record<string, unknown>;
};

const BASE = "/api/v1/populations";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init);
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
      else if (body.detail) detail = JSON.stringify(body.detail).slice(0, 300);
    } catch {
      // keep status
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const popApi = {
  list: () => request<PopVersion[]>(""),
  preset: () => request<Record<string, unknown>>("/presets"),
  detail: (id: number) => request<VersionDetail>(`/versions/${id}`),
  personas: (id: number, offset: number, q: string) =>
    request<{ total: number; items: Persona[] }>(
      `/versions/${id}/personas?offset=${offset}&limit=25${q ? `&q=${encodeURIComponent(q)}` : ""}`,
    ),
  create: (body: unknown) =>
    request<PopVersion>("", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  importFile: (name: string, file: File) =>
    request<PopVersion>(`/import?name=${encodeURIComponent(name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/x-ndjson" },
      body: file,
    }),
  exportUrl: (id: number, format: "jsonl" | "csv") => `${BASE}/versions/${id}/export?format=${format}`,
};
