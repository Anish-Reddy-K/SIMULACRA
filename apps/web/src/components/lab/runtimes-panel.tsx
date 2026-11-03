"use client";

import { ApiError, Loading, Panel } from "@/components/lab/ui";
import { Badge } from "@/components/ui/badge";
import { labApi } from "@/lib/lab-api";
import { formatBytes } from "@/lib/format";
import { useApi } from "@/lib/use-api";

const INSTALL_HINT: Record<string, string> = {
  ollama: "Download from ollama.com, then run: ollama serve",
  "llama.cpp": "brew install llama.cpp, then run llama-server -m <model.gguf> --port 8080",
  "mlx-lm": "uv tool install mlx-lm, then run mlx_lm.server --model <mlx model> --port 8000",
  "vllm-mlx": "uv tool install vllm-mlx, then run vllm-mlx serve <model> --continuous-batching",
};

export function RuntimesPanel() {
  const { data, error, loading, reload } = useApi(labApi.runtimes);
  if (loading) return <Loading what="runtimes" />;
  if (error || !data) return <ApiError error={error ?? "No data"} onRetry={reload} />;
  const running = data.runtimes.filter((r) => r.running);
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <Panel title="Installed runtimes">
        <ul className="flex flex-col gap-3">
          {data.installed.map((b) => (
            <li key={b.name} className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <span className="font-medium">{b.name}</span>
                <Badge variant={b.path ? "secondary" : "outline"}>
                  {b.path ? "Installed" : "Not installed"}
                </Badge>
              </div>
              {!b.path && <span className="text-xs text-muted-foreground">{INSTALL_HINT[b.name]}</span>}
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-muted-foreground">
          Simulacra detects runtimes but never installs or starts them for you.
        </p>
      </Panel>
      <Panel title="Running now">
        {running.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No local inference server is answering. Start one of the runtimes on the left, then
            refresh.
          </p>
        ) : (
          <ul className="flex flex-col gap-4">
            {running.map((r) => (
              <li key={r.base_url} className="flex flex-col gap-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{r.info?.kind}</span>
                  <span className="font-mono text-xs text-muted-foreground">{r.base_url}</span>
                  {r.info?.version && (
                    <Badge variant="outline">{/^\d/.test(r.info.version) ? `v${r.info.version}` : r.info.version}</Badge>
                  )}
                </div>
                <span className="text-xs text-muted-foreground">
                  JSON-schema output:{" "}
                  {r.info?.capabilities.json_schema === null ? "unknown until tested" : r.info?.capabilities.json_schema ? "supported" : "not supported"}
                  {r.info?.capabilities.parallel_slots ? ` - ${r.info.capabilities.parallel_slots} parallel slots` : ""}
                </span>
                <ul className="mt-1 flex flex-col gap-0.5 text-sm">
                  {r.models.map((m) => (
                    <li key={m.name} className="flex justify-between gap-3">
                      <span className="min-w-0 truncate font-mono text-xs">{m.name}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {[m.parameter_size, m.quantization, m.size_bytes ? formatBytes(m.size_bytes) : null]
                          .filter(Boolean)
                          .join(" - ")}
                      </span>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
