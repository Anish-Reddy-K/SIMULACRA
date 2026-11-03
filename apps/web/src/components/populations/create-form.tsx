"use client";

import { useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/lab/ui";
import { labApi } from "@/lib/lab-api";
import { popApi, type PopVersion } from "@/lib/pop-api";
import { useApi } from "@/lib/use-api";

export function CreateForm({ onCreated }: { onCreated: (v: PopVersion) => void }) {
  const preset = useApi(popApi.preset);
  const runtimes = useApi(labApi.runtimes);
  const [name, setName] = useState("My population");
  const [size, setSize] = useState("100");
  const [seed, setSeed] = useState("1");
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const models = (runtimes.data?.runtimes ?? [])
    .filter((r) => r.running && r.info)
    .flatMap((r) =>
      r.models.map((m) => ({
        key: `${r.base_url}|${m.name}`,
        label: `${r.info?.kind} / ${m.name}`,
        base_url: r.base_url,
        model: m.name,
        mode: r.info?.capabilities.json_schema === null ? "prompted" : "constrained",
      })),
    );

  async function create() {
    if (!preset.data) return;
    setBusy(true);
    setProblem(null);
    const chosen = models.find((m) => m.key === target);
    try {
      const v = await popApi.create({
        spec: { ...preset.data, name, size: Number(size), seed: Number(seed) },
        enrich: chosen
          ? { target: { base_url: chosen.base_url, model: chosen.model, structured_mode: chosen.mode }, concurrency: 1 }
          : null,
      });
      onCreated(v);
    } catch (e) {
      setProblem(e instanceof Error ? e.message : "Could not create the population");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Generate a population">
      <div className="grid gap-4 md:grid-cols-3">
        <label className="flex flex-col gap-1 text-sm">
          Name
          <Input value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Number of personas (1 to 10000)
          <Input type="number" min={1} max={10000} value={size} onChange={(e) => setSize(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Seed
          <Input type="number" value={seed} onChange={(e) => setSeed(e.target.value)} />
        </label>
      </div>
      <label className="mt-4 flex flex-col gap-1 text-sm">
        Write biographies with a local model (optional)
        <select
          className="h-10 rounded-lg border border-input bg-card px-2"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        >
          <option value="">No - use deterministic template biographies (fast)</option>
          {models.map((m) => (
            <option key={m.key} value={m.key}>
              {m.label}
            </option>
          ))}
        </select>
      </label>
      <p className="mt-2 text-xs text-muted-foreground">
        Demographics are sampled by code from the starting distribution below, which is an
        illustrative assumption and not census data. The model only writes text around the sampled
        facts. Biographies from a local model take a few seconds each.
      </p>
      {problem && (
        <Alert variant="destructive" role="alert" className="mt-4">
          <AlertTitle>Could not generate</AlertTitle>
          <AlertDescription>{problem}</AlertDescription>
        </Alert>
      )}
      <div className="mt-4">
        <Button onClick={create} disabled={busy || !preset.data || !name.trim()}>
          {busy ? "Generating..." : "Generate"}
        </Button>
      </div>
    </Panel>
  );
}

export function ImportForm({ onCreated }: { onCreated: (v: PopVersion) => void }) {
  const [name, setName] = useState("Imported population");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function run() {
    if (!file) return;
    setBusy(true);
    setProblem(null);
    try {
      onCreated(await popApi.importFile(name, file));
    } catch (e) {
      setProblem(e instanceof Error ? e.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Import a population">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm">
          Name
          <Input value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          File (.jsonl exported from Simulacra)
          <input
            type="file"
            accept=".jsonl,application/x-ndjson"
            className="min-h-10 rounded-lg border border-input bg-card p-2 text-sm"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        Imported text is treated as data only: it is validated, size-limited, and never executed.
      </p>
      {problem && (
        <Alert variant="destructive" role="alert" className="mt-4">
          <AlertTitle>Import failed</AlertTitle>
          <AlertDescription>{problem}</AlertDescription>
        </Alert>
      )}
      <div className="mt-4">
        <Button variant="outline" onClick={run} disabled={!file || busy}>
          {busy ? "Importing..." : "Import"}
        </Button>
      </div>
    </Panel>
  );
}
