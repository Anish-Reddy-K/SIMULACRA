export function formatMb(mb: number | null | undefined): string {
  if (mb === null || mb === undefined) return "not measured";
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${Math.round(mb)} MB`;
}

export function formatBytes(bytes: number | null | undefined): string {
  return bytes ? formatMb(bytes / 2 ** 20) : "unknown";
}

export function formatNumber(value: number | null | undefined, digits = 1, unit = ""): string {
  if (value === null || value === undefined) return "not measured";
  return `${value.toFixed(digits)}${unit}`;
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "not measured";
  return `${Math.round(value * 100)}%`;
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  return `${m}m ${Math.round(seconds % 60)}s`;
}

export const EVIDENCE_LABEL: Record<string, string> = {
  screened: "Compatibility only",
  quick: "Quick (indicative)",
  detailed: "Detailed",
  soak: "Sustained run",
};
