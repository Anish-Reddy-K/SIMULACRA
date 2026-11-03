"""Reproducible research studies on the simulation itself (Phase 11).

Runs against a running Simulacra API (`make up`) and a local runtime. Each study uses a normal
experiment, so the results are stored, auditable and exportable like any other run.

    uv run python scripts/run_evaluation.py --base-url http://127.0.0.1:8080 --model qwen2.5-3b \
        --second-base-url http://127.0.0.1:8081 --second-model qwen2.5-1.5b --personas 100

Studies:
  prompt-sensitivity   the same persona sees the same offer described in three equivalent ways
  repeat-stability     the same prompt run several times per persona (run-to-run variation)
  model-disagreement   two models answer identical trials (needs --second-*)
Outputs are written to docs/evaluation/results.json.
"""

import argparse
import json
import time
import urllib.request
from pathlib import Path
from typing import Any

API = "http://127.0.0.1:8765/api/v1"
DESCRIPTION = (
    "A self-heating smart mug that keeps coffee or tea at your chosen temperature for up to "
    "6 hours, with a charging coaster and a phone app."
)
PARAPHRASES = [
    DESCRIPTION,
    "WarmMug is a mug with a built-in heater and a companion app. You set a temperature and it "
    "holds your drink there for as long as six hours; a charging coaster powers it.",
    "Meet a coffee mug that never goes cold: choose your preferred temperature in the app, and the "
    "battery-powered mug maintains it for roughly six hours, recharging on its coaster.",
]


def call(path: str, body: Any = None, post: bool = False) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        API + path, data=data, headers={"Content-Type": "application/json"},
        method="POST" if (body is not None or post) else "GET",
    )
    return json.load(urllib.request.urlopen(req, timeout=600))  # noqa: S310  (local API)


def wait(run_id: int) -> dict[str, Any]:
    while True:
        run = call(f"/runs/{run_id}")
        if run["state"] in ("completed", "completed_with_errors", "failed", "cancelled"):
            return run  # type: ignore[no-any-return]
        time.sleep(5)


def population(size: int, seed: int) -> int:
    preset = call("/populations/presets")
    return int(call("/populations", {"spec": {**preset, "name": f"Evaluation population {size}", "size": size, "seed": seed}})["id"])


def start(exp: dict[str, Any], base_url: str, model: str, **opts: Any) -> int:
    target = {"base_url": base_url, "model": model, "structured_mode": "constrained"}
    return int(call(f"/experiments/{exp['id']}/start", {"target": target, "concurrency": 12, "batch_size": 24,
                                                         "prompt_variant": "v2", **opts})["run_id"])


def base_experiment(name: str, pop: int, **over: Any) -> dict[str, Any]:
    body = {
        "name": name, "research_question": "Evaluation study", "population_version_id": pop,
        "scenario": {"product_name": "WarmMug", "description": DESCRIPTION, "price_usd": 79, "category": "kitchen gadgets"},
        "seed": 7, **over,
    }
    return call("/experiments", body)  # type: ignore[no-any-return]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8080")
    ap.add_argument("--model", default="qwen2.5-3b")
    ap.add_argument("--second-base-url")
    ap.add_argument("--second-model")
    ap.add_argument("--personas", type=int, default=100)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--out", default="docs/evaluation/results.json")
    args = ap.parse_args()
    pop = population(args.personas, 55)
    results: dict[str, Any] = {"personas": args.personas, "model": args.model, "studies": {}}

    # 1. Prompt sensitivity: within-subjects, three equivalent descriptions of the same offer.
    exp = call("/experiments", {
        "name": "Prompt sensitivity", "research_question": "Does equivalent rewording change answers?",
        "population_version_id": pop, "design": "within", "seed": 7,
        "scenario": {"product_name": "WarmMug", "description": DESCRIPTION, "price_usd": 79, "category": "kitchen gadgets"},
        "treatments": [{"label": f"Wording {chr(65 + i)}", "params": {"description": d}} for i, d in enumerate(PARAPHRASES)],
    })
    rid = start(exp, args.base_url, args.model)
    wait(rid)
    results["studies"]["prompt_sensitivity"] = {"run_id": rid, "comparison": call(f"/runs/{rid}/comparison"),
                                                "results": call(f"/runs/{rid}/results")["treatments"]}

    # 2. Repeat stability: identical prompts, several repeats per persona.
    exp = base_experiment("Repeat stability", pop, repeats=args.repeats)
    rid = start(exp, args.base_url, args.model)
    wait(rid)
    results["studies"]["repeat_stability"] = {"run_id": rid, "stability": call(f"/runs/{rid}/results")["repeat_stability"]}

    # 3. Model disagreement: identical trials, two models.
    if args.second_base_url and args.second_model:
        exp = base_experiment("Model disagreement", pop)
        a = start(exp, args.base_url, args.model)
        wait(a)
        b = start(exp, args.second_base_url, args.second_model)
        wait(b)
        results["studies"]["model_disagreement"] = {"run_a": a, "run_b": b, "comparison": call(f"/compare-runs?a={a}&b={b}")}

    Path(args.out).write_text(json.dumps(results, indent=1))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
