"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { ApiError, Loading, Panel } from "@/components/lab/ui";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { expApi } from "@/lib/exp-api";
import { labApi } from "@/lib/lab-api";
import { popApi } from "@/lib/pop-api";
import { useApi } from "@/lib/use-api";

const STEPS = ["Question", "Population", "Offer", "Model", "Review"] as const;

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium">{label}</span>
      {children}
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </label>
  );
}

export function Wizard() {
  const router = useRouter();
  const pops = useApi(popApi.list);
  const runtimes = useApi(labApi.runtimes);
  const recs = useApi(labApi.recommendations);
  const [step, setStep] = useState(0);
  const [name, setName] = useState("Concept test");
  const [question, setQuestion] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [popId, setPopId] = useState("");
  const [product, setProduct] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [category, setCategory] = useState("");
  const [targetKey, setTargetKey] = useState("");
  const [repeats, setRepeats] = useState("1");
  const [seed, setSeed] = useState("1");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const readyPops = (pops.data ?? []).filter((p) => p.status === "ready");
  const models = useMemo(
    () =>
      (runtimes.data?.runtimes ?? [])
        .filter((r) => r.running && r.info)
        .flatMap((r) =>
          r.models.map((m) => ({
            key: `${r.base_url}|${m.name}`,
            label: `${r.info?.kind} / ${m.name}`,
            base_url: r.base_url,
            model: m.name,
            mode: r.info?.capabilities.json_schema === null ? "prompted" : "constrained",
          })),
        ),
    [runtimes.data],
  );
  const pop = readyPops.find((p) => String(p.id) === popId);
  const target = models.find((m) => m.key === targetKey);
  const fastest = recs.data?.find((r) => r.goal === "balanced")?.selected ?? null;
  const measured = fastest && target && fastest.label.includes(target.model) ? fastest.valid_per_min : null;
  const trials = (pop?.size ?? 0) * Number(repeats || 1);
  const eta = measured && trials ? Math.round(trials / measured) : null;

  const stepValid = [
    name.trim() !== "" && question.trim().length >= 3,
    !!pop,
    product.trim() !== "" && description.trim().length >= 10,
    !!target,
    true,
  ];

  async function launch() {
    if (!pop || !target) return;
    setBusy(true);
    setProblem(null);
    try {
      const exp = await expApi.create({
        name,
        kind: "product_concept",
        research_question: question,
        hypothesis,
        population_version_id: pop.id,
        scenario: {
          product_name: product,
          description,
          price_usd: price === "" ? null : Number(price),
          category: category || null,
        },
        repeats: Number(repeats),
        seed: Number(seed),
      });
      const started = await expApi.start(exp.id, {
        target: { base_url: target.base_url, model: target.model, structured_mode: target.mode },
        concurrency: 4,
      });
      router.push(`/runs/view/?id=${started.run_id}`);
    } catch (e) {
      setProblem(e instanceof Error ? e.message : "Could not start the experiment");
      setBusy(false);
    }
  }

  if (pops.loading || runtimes.loading) return <Loading what="options" />;
  if (pops.error) return <ApiError error={pops.error} onRetry={pops.reload} />;

  return (
    <div className="flex flex-col gap-6">
      <ol aria-label="Steps" className="flex flex-wrap gap-2 text-sm">
        {STEPS.map((s, i) => (
          <li key={s} aria-current={i === step ? "step" : undefined} className={`rounded-lg border px-3 py-1 ${i === step ? "border-primary bg-accent font-medium text-accent-foreground" : "border-hairline text-muted-foreground"}`}>
            {i + 1}. {s}
          </li>
        ))}
      </ol>

      {step === 0 && (
        <Panel title="1. What do you want to learn?">
          <div className="flex flex-col gap-4">
            <Field label="Experiment name"><Input value={name} maxLength={120} onChange={(e) => setName(e.target.value)} /></Field>
            <Field label="Research question" hint="For example: would busy professionals pay for a self-heating mug?">
              <Input value={question} maxLength={500} onChange={(e) => setQuestion(e.target.value)} />
            </Field>
            <Field label="Hypothesis (optional)" hint="What you expect to find. It is recorded, not used to steer the model.">
              <Input value={hypothesis} maxLength={500} onChange={(e) => setHypothesis(e.target.value)} />
            </Field>
          </div>
        </Panel>
      )}

      {step === 1 && (
        <Panel title="2. Who are the simulated people?">
          {readyPops.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No population is ready yet. Create one in <a className="underline" href="/populations/">Populations</a> first.
            </p>
          ) : (
            <Field label="Population" hint="Generated from an assumed distribution, not a representative sample of real people.">
              <select className="h-10 rounded-lg border border-input bg-card px-2" value={popId} onChange={(e) => setPopId(e.target.value)}>
                <option value="">Choose a population</option>
                {readyPops.map((p) => (
                  <option key={p.id} value={p.id}>{p.name} v{p.version} ({p.size} personas)</option>
                ))}
              </select>
            </Field>
          )}
        </Panel>
      )}

      {step === 2 && (
        <Panel title="3. What are they shown?">
          <div className="flex flex-col gap-4">
            <Field label="Product name"><Input value={product} maxLength={120} onChange={(e) => setProduct(e.target.value)} /></Field>
            <Field label="Description" hint="At least a sentence. Describe what it is and what it does.">
              <textarea className="min-h-24 rounded-lg border border-input bg-muted p-2 text-sm" maxLength={1500} value={description} onChange={(e) => setDescription(e.target.value)} />
            </Field>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Price in USD (optional)"><Input type="number" min={0} value={price} onChange={(e) => setPrice(e.target.value)} /></Field>
              <Field label="Category (optional)"><Input value={category} maxLength={80} onChange={(e) => setCategory(e.target.value)} /></Field>
            </div>
          </div>
        </Panel>
      )}

      {step === 3 && (
        <Panel title="4. Which local model runs it?">
          {models.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No local runtime with models is running. Start one (see the <a className="underline" href="/lab/">Inference Lab</a>).
            </p>
          ) : (
            <>
              <Field label="Model and runtime" hint={fastest ? `Inference Lab best-balanced pick: ${fastest.label}` : "Run a benchmark in the Inference Lab to get a measured recommendation."}>
                <select className="h-10 rounded-lg border border-input bg-card px-2" value={targetKey} onChange={(e) => setTargetKey(e.target.value)}>
                  <option value="">Choose a model</option>
                  {models.map((m) => (<option key={m.key} value={m.key}>{m.label}</option>))}
                </select>
              </Field>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <Field label="Repeats per persona" hint="More repeats measure run-to-run variation."><Input type="number" min={1} max={20} value={repeats} onChange={(e) => setRepeats(e.target.value)} /></Field>
                <Field label="Seed"><Input type="number" value={seed} onChange={(e) => setSeed(e.target.value)} /></Field>
              </div>
            </>
          )}
        </Panel>
      )}

      {step === 4 && (
        <Panel title="5. Review and start">
          <dl className="grid gap-3 text-sm md:grid-cols-2">
            <div><dt className="text-xs text-muted-foreground">Question</dt><dd>{question}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Population</dt><dd>{pop?.name} v{pop?.version} ({pop?.size} personas)</dd></div>
            <div><dt className="text-xs text-muted-foreground">Offer</dt><dd>{product}{price ? ` at $${price}` : ""}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Model</dt><dd className="font-mono">{target?.label}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Trials</dt><dd>{trials}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Estimated time</dt><dd>{eta ? `about ${eta} min, from your benchmark` : "unknown - no benchmark for this model yet"}</dd></div>
          </dl>
          <p className="mt-3 text-xs text-muted-foreground">
            The exact configuration is frozen when you start so the run can be reproduced and audited. Runs continue in the
            background if you close this page.
          </p>
          {problem && (
            <Alert variant="destructive" role="alert" className="mt-4">
              <AlertTitle>Could not start</AlertTitle>
              <AlertDescription>{problem}</AlertDescription>
            </Alert>
          )}
        </Panel>
      )}

      <div className="flex gap-3">
        <Button variant="outline" disabled={step === 0 || busy} onClick={() => setStep(step - 1)}>Back</Button>
        {step < STEPS.length - 1 ? (
          <Button disabled={!stepValid[step]} onClick={() => setStep(step + 1)}>Next</Button>
        ) : (
          <Button disabled={busy || !stepValid.every(Boolean)} onClick={() => void launch()}>
            {busy ? "Starting..." : "Start experiment"}
          </Button>
        )}
      </div>
    </div>
  );
}
