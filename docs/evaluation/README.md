# Scientific evaluation: how far can this simulation be trusted?

This is the honest answer so far: **not very far with small local models, and nothing here has been checked against real human data.** Positive and negative findings are published together. Raw outputs: `results.json` (this folder), `../benchmarks/raw/`, `../examples/`, and the app's run history.

## Summary of findings
| Question | Finding | Evidence |
|---|---|---|
| Are results reproducible? | Configuration and raw outputs are, bit-identical regeneration is not. At temperature 0.7 only **72%** of personas gave the same top-2-box answer across 5 repeats of an identical prompt, and **41%** gave the same exact intent. | repeat-stability study below |
| Does equivalent rewording change answers? | Aggregate top-2-box moved little (22%, 19%, 18%; no detectable difference, Holm p = 0.85), but **15% of individual personas changed their answer** between two wordings of the same offer. | prompt-sensitivity study |
| Do different models agree? | **No.** On identical trials the 3B model gave top-2-box for 22% of personas and the 1.5B model for 89%. Persona-level agreement was 33%, Cohen's kappa **0.07** (near chance), and mean appeal differed by 1.3 points (p < 1e-30). Model choice can reverse a conclusion. | model-disagreement study |
| Do personas respect hard constraints? | Budget-constraint checks passed (no constrained persona said "buy now" at $600), but a degenerate model would pass them trivially. The responsiveness guard showed **all five tested configurations failed to ever say "buy now" for an affluent persona at $50**. | benchmark invariants (`../benchmark-results.md`) |
| Is price sensitivity visible? | Not at 100 personas per arm: simulated interest was 8.6%, 15.8%, 11.3% at $49, $79, $129 (non-monotone, no detectable differences). | `../ab-testing.md` |
| Is the population diverse? | Demographics follow the specified assumptions (diagnostics report fidelity). Model-written biographies are **homogeneous**: lexical variety (distinct-1) fell from 0.128 at 100 personas to 0.026 at 1,000, and the biographies restate the sampled facts more than they add individuality. | `../populations.md`, population diagnostics |
| Does it agree with real people? | **Unknown.** No real human dataset has been evaluated. | below |

## The studies (100 personas, Qwen2.5 3B Q4_K_M via llama.cpp unless stated, prompt v2)

### 1. Prompt sensitivity (within-subjects, run 25)
The same 100 personas each saw the same offer described three equivalent ways, analyzed as matched pairs.

| Wording | Top-2-box | Mean appeal |
|---|---|---|
| A (original) | 22% | 2.51 |
| B | 19% | 2.63 |
| C | 18% | 2.55 |

Exact McNemar tests: B vs A 7 vs 10 discordant personas, Holm p = 0.85; C vs A 5 vs 9, Holm p = 0.85. Appeal B vs A differed by 0.12 (p = 0.02 unadjusted, not corrected for multiple comparisons). So the average effect of rewording is small compared with noise, but about one persona in seven changes its answer, which is the same order as the run-to-run variation below.

### 2. Repeat stability (run 26)
Identical prompt, temperature 0.7, 5 repeats per persona: top-2-box agreement across all repeats 72%; exact purchase-intent agreement 41%. A single run of this simulation is one draw from a noisy process; use repeats to measure the noise.

### 3. Model disagreement (runs 27 and 28)
Identical trials (same personas, same prompts), two models: Qwen2.5 3B (22% top-2-box, mean appeal 2.51) and Qwen2.5 1.5B (89%, mean appeal 3.83). Same top-2 answer for 33% of personas, kappa 0.067, McNemar p < 0.001 (67 personas positive only under the 1.5B model, none the other way), same main objection for 48%. The smaller model is far more agreeable, matching the over-agreement documented for synthetic respondents.

## What was not done
- **No real-data evaluation.** The pipeline exists and is tested (`simulacra/evaluation/real_data.py`, `scripts/evaluate_real_data.py`): it joins a real-respondent CSV to simulated segments and reports error, bias, rank correlation, calibration slope and intercept, a variation ratio (compressed variation) and the worst segments. It was exercised end to end only on a small **synthetic CSV invented for the demonstration**, whose output is not evidence about anything. Publishing a real result requires a real dataset and its license.
- Larger models, other prompts and other product categories were not studied.
- Calibration of individual-level probabilities was not measured (the simulation does not produce them).

## Context from the literature (secondary summaries; primary papers to be re-read before citing)
Park et al. report that agents built from long interviews reached about 85% of the participants' own test-retest agreement while demographic-only agents scored about 70 to 71%; Pew (Sept 2026) found "digital twin" respondents missed real survey answers by about 12 points on average and compressed opinion diversity. Our small-model results (low behavioral grounding, large model disagreement) point the same direction and show why calibration against real data is required before any decision-making use.

## Reproduce
```sh
make up                                            # in one terminal, with a runtime serving models
uv run python scripts/run_evaluation.py --base-url http://127.0.0.1:8080 --model qwen2.5-3b \
  --second-base-url http://127.0.0.1:8081 --second-model qwen2.5-1.5b --personas 100
uv run python scripts/evaluate_real_data.py --run <id> --csv real.csv --outcome would_buy --attributes region,age_band
```
Studies run as normal experiments, so every trial can be inspected in the app.
