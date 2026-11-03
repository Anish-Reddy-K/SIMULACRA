# WarmMug concept test

> Simulated results. Not observed human behavior and not a validated prediction.

## Executive summary

- 100 of 100 simulated responses were valid (100% valid output).
- Baseline: 5% (5 of 100) of simulated respondents said probably or definitely (sampling variation 2% to 11%); mean appeal 2.5 of 5.
- The most common objection was 'price' (84% of valid responses).
- The most common perceived benefit was 'convenience' (37%).

## Research question

Would busy professionals buy a self-heating smart mug?

**Hypothesis:** Interest is higher among early adopters and higher-income personas; price will be the main objection.

## Experiment configuration

- Treatments: Baseline
- Trials planned: 100  (valid 100)
- Prompt version: concept-v1 (33cb8835fdc8)

## Inference model and runtime

- Runtime: llama.cpp b11960-8642541b2
- Model: qwen2.5-3b (digest None, quantization None)
- Temperature 0.7, seed 7, structured mode constrained

## Simulated findings

### Baseline (n=100)

| Purchase intent | n | share |
|---|---|---|
| definitely | 1 | 1% |
| probably | 4 | 4% |
| unsure | 20 | 20% |
| probably not | 73 | 73% |
| definitely not | 2 | 2% |

## Segment analysis

| Segment | Treatment | n | Top-2-box | Sampling variation |
|---|---|---|---|---|
| age_band=18-29 | 0 | 18 | 0% | 0% to 18% |
| age_band=30-44 | 0 | 29 | 3% | 1% to 17% |
| age_band=45-59 | 0 | 22 | 5% | 1% to 22% |
| age_band=60+ | 0 | 31 | 10% | 3% to 25% |
| education=bachelor | 0 | 32 | 9% | 3% to 24% |
| education=high_school | 0 | 25 | 4% | 1% to 20% |
| education=some_college | 0 | 26 | 0% | 0% to 13% |
| employment=full_time | 0 | 61 | 7% | 3% to 16% |
| employment=part_time | 0 | 10 | 0% | 0% to 28% |
| employment=retired | 0 | 11 | 9% | 2% to 38% |
| employment=self_employed | 0 | 12 | 0% | 0% to 24% |
| gender=man | 0 | 49 | 6% | 2% to 17% |
| gender=woman | 0 | 51 | 4% | 1% to 13% |
| household=couple | 0 | 26 | 4% | 1% to 19% |
| household=family_with_children | 0 | 36 | 3% | 0% to 14% |
| household=lives_alone | 0 | 14 | 14% | 4% to 40% |
| household=shared_housing | 0 | 19 | 5% | 1% to 25% |
| income_band=high | 0 | 14 | 7% | 1% to 31% |
| income_band=low | 0 | 24 | 0% | 0% to 14% |
| income_band=middle | 0 | 24 | 0% | 0% to 14% |
| income_band=upper_middle | 0 | 25 | 16% | 6% to 35% |
| income_band=very_low | 0 | 13 | 0% | 0% to 23% |
| price_sensitivity=high | 0 | 41 | 2% | 0% to 13% |
| price_sensitivity=low | 0 | 15 | 13% | 4% to 38% |
| price_sensitivity=moderate | 0 | 33 | 6% | 2% to 20% |
| price_sensitivity=very_high | 0 | 11 | 0% | 0% to 26% |
| region=midwest | 0 | 21 | 10% | 3% to 29% |
| region=northeast | 0 | 17 | 6% | 1% to 27% |
| region=south | 0 | 38 | 3% | 0% to 13% |
| region=west | 0 | 24 | 4% | 1% to 20% |
| tech_adoption=early_adopter | 0 | 26 | 12% | 4% to 29% |
| tech_adoption=early_majority | 0 | 25 | 4% | 1% to 20% |
| tech_adoption=laggard | 0 | 18 | 0% | 0% to 18% |
| tech_adoption=late_majority | 0 | 29 | 3% | 1% to 17% |

_Segments with fewer than 10 valid responses are hidden._

## Top objections

- price: 84 (84%)
- already have alternative: 5 (5%)

## Representative responses

- "I don't want to spend that much on a mug when I can get a good cup for less." (objection: price; source trial #1, persona P2-00001)
- "I can't afford a $79 mug, especially since we're on a tight budget with kids to support." (objection: price; source trial #2, persona P2-00002)
- "I already have a reliable way to keep my drinks warm, so this gadget doesn't seem like a necessity to me." (objection: already have alternative; source trial #3, persona P2-00003)
- "I already have a good coffee mug that keeps my drinks warm, so why invest in this fancy smart mug?" (objection: already have alternative; source trial #6, persona P2-00005)
- "I don't want to spend that much on a mug when I can get a good cup for less." (benefit: convenience; source trial #1, persona P2-00001)
- "I already have a reliable way to keep my drinks warm, so this gadget doesn't seem like a necessity to me." (benefit: convenience; source trial #3, persona P2-00003)
- "I can't afford a $79 mug, especially since we're on a tight budget with kids to support." (benefit: saves money; source trial #2, persona P2-00002)
- "I already have a good coffee mug that keeps my drinks warm, so why invest in this fancy smart mug?" (benefit: saves money; source trial #6, persona P2-00005)
- "I don't have much money to waste on gadgets, and this thing costs too much." (benefit: saves time; source trial #5, persona P2-00006)
- "I'm too old and tech-phobic to understand how to use this, and I don't need something that complicated in my simple life." (benefit: saves time; source trial #7, persona P2-00007)

## Contradictory patterns

- none detected by the configured checks

## Limitations

- These are simulated opinions from model-generated personas. They are not observed human behavior and not validated predictions.
- Personas follow an assumed distribution, not a representative sample of any real population.
- Small local language models tend to agree with offers, give generic reasons and under-represent real variation in opinion; results can depend strongly on prompt wording and on the model.
- Intervals describe sampling variation of this simulation only. They are not confidence in real-world behavior.
- Stated purchase intent is not purchase behavior, even among real people.

## Suggested real-world follow-up

- Treat the objections and segment differences as hypotheses and check them with real customer interviews or a small real survey.
- If a treatment difference matters to a decision, test it with real traffic (for example an A/B test on a landing page) before acting.
- Re-run with a different model and prompt wording; findings that change are artifacts, not insights.

## Reproducibility metadata

```json
{
  "simulacra_version": "0.1.0",
  "experiment": {
    "id": 1,
    "name": "WarmMug concept test",
    "kind": "product_concept",
    "research_question": "Would busy professionals buy a self-heating smart mug?",
    "hypothesis": "Interest is higher among early adopters and higher-income personas; price will be the main objection.",
    "scenario": {
      "product_name": "WarmMug",
      "description": "A self-heating smart mug that keeps coffee or tea at your chosen temperature for up to 6 hours, with a charging coaster and a phone app.",
      "price_usd": 79.0,
      "category": "kitchen gadgets",
      "headline": null
    },
    "config": {
      "design": "between",
      "repeats": 1,
      "seed": 7
    },
    "treatments": [
      {
        "idx": 0,
        "label": "Baseline",
        "params": {}
      }
    ]
  },
  "population": {
    "version_id": 2,
    "version": 1,
    "size": 100,
    "seed": 11,
    "source": "generated",
    "spec_sha256_16": "f5dd3c9998b061a3"
  },
  "inference": {
    "runtime": "llama.cpp",
    "runtime_version": "b11960-8642541b2",
    "base_url": "http://127.0.0.1:8080",
    "model": "qwen2.5-3b",
    "model_digest": null,
    "quantization": null,
    "structured_mode": "constrained",
    "temperature": 0.7,
    "max_tokens": 220,
    "concurrency": 4,
    "seed": 7
  },
  "prompt": {
    "version": "concept-v1",
    "sha256_12": "33cb8835fdc8"
  },
  "trials_planned": 100,
  "hardware": {
    "captured_at": "2026-11-03T00:46:37.032543Z",
    "os": "Darwin",
    "os_version": "26.5.2",
    "arch": "arm64",
    "chip": "Apple M4",
    "apple_silicon": true,
    "cpu_cores_total": 10,
    "cpu_cores_performance": 4,
    "ram_total_mb": 16384,
    "ram_available_mb": 2586,
    "swap_used_mb": 6935,
    "disk_free_mb": 12639,
    "disk_total_mb": 233752,
    "metal": "Metal 4",
    "on_battery": false,
    "low_power_mode": false,
    "sleep_prevented": true,
    "notes": []
  }
}
```
