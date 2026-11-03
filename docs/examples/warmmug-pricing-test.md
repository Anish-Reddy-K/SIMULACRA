# WarmMug pricing test

> Simulated results. Not observed human behavior and not a validated prediction.

## Executive summary

- 300 of 300 simulated responses were valid (100% valid output).
- $49: 9% (8 of 93) of simulated respondents said probably or definitely (sampling variation 4% to 16%); mean appeal 2.5 of 5.
- $79: 16% (16 of 101) of simulated respondents said probably or definitely (sampling variation 10% to 24%); mean appeal 2.6 of 5.
- $129: 11% (12 of 106) of simulated respondents said probably or definitely (sampling variation 7% to 19%); mean appeal 2.6 of 5.
- $79 versus $49: top-2-box differs by +7 points (sampling variation -2 to +17 points where available; Holm-adjusted p = 0.269), no statistically detectable difference between simulated responses.
- $129 versus $49: top-2-box differs by +3 points (sampling variation -6 to +11 points where available; Holm-adjusted p = 0.639), no statistically detectable difference between simulated responses.
- The most common objection was 'price' (84% of valid responses).
- The most common perceived benefit was 'saves money' (48%).

## Research question

How does the price of a self-heating smart mug change simulated purchase interest?

**Hypothesis:** Interest should fall as price rises; a $129 price should be clearly less attractive than $49.

## Experiment configuration

- Treatments: $49, $79, $129
- Trials planned: 300  (valid 300)
- Prompt version: concept-v1 (33cb8835fdc8)

## Inference model and runtime

- Runtime: llama.cpp b11960-8642541b2
- Model: qwen2.5-3b (digest None, quantization None)
- Temperature 0.7, seed 3, structured mode constrained

## Simulated findings

### $49 (n=93)

| Purchase intent | n | share |
|---|---|---|
| definitely | 0 | 0% |
| probably | 8 | 9% |
| unsure | 14 | 15% |
| probably not | 71 | 76% |
| definitely not | 0 | 0% |

### $79 (n=101)

| Purchase intent | n | share |
|---|---|---|
| definitely | 4 | 4% |
| probably | 12 | 12% |
| unsure | 7 | 7% |
| probably not | 77 | 76% |
| definitely not | 1 | 1% |

### $129 (n=106)

| Purchase intent | n | share |
|---|---|---|
| definitely | 7 | 7% |
| probably | 5 | 5% |
| unsure | 8 | 8% |
| probably not | 85 | 80% |
| definitely not | 1 | 1% |

## Treatment comparison

| Treatment | vs | Top-2-box | Baseline | Difference | Holm p | Cohen's h |
|---|---|---|---|---|---|---|
| $79 | $49 | 16% | 9% | +7.2 pts | 0.269 | 0.22 |
| $129 | $49 | 11% | 9% | +2.7 pts | 0.639 | 0.09 |

Simulated purchase interest by price:

- $49: 9% (n=93)
- $79: 16% (n=101)
- $129: 11% (n=106)
- Simulated purchase interest by price. This is not real demand and not a price elasticity.

Randomization balance: smallest Holm-adjusted p = 0.491 (no detectable imbalance)

_Segment comparisons are exploratory, require at least 10 valid responses in each arm, and are Holm-adjusted across all 61 tests._
_Differences are differences between simulated responses. A significant result means the model responded differently, not that real people would._

## Segment analysis

| Segment | Treatment | n | Top-2-box | Sampling variation |
|---|---|---|---|---|
| age_band=18-29 | 0 | 16 | 6% | 1% to 28% |
| age_band=18-29 | 1 | 15 | 7% | 1% to 30% |
| age_band=18-29 | 2 | 20 | 15% | 5% to 36% |
| age_band=30-44 | 0 | 18 | 6% | 1% to 26% |
| age_band=30-44 | 1 | 23 | 26% | 13% to 46% |
| age_band=30-44 | 2 | 25 | 0% | 0% to 13% |
| age_band=45-59 | 0 | 29 | 7% | 2% to 22% |
| age_band=45-59 | 1 | 36 | 17% | 8% to 32% |
| age_band=45-59 | 2 | 34 | 18% | 8% to 34% |
| age_band=60+ | 0 | 30 | 13% | 5% to 30% |
| age_band=60+ | 1 | 27 | 11% | 4% to 28% |
| age_band=60+ | 2 | 27 | 11% | 4% to 28% |
| education=bachelor | 0 | 26 | 4% | 1% to 19% |
| education=bachelor | 1 | 29 | 21% | 10% to 38% |
| education=bachelor | 2 | 29 | 17% | 8% to 35% |
| education=graduate | 0 | 11 | 27% | 10% to 57% |
| education=graduate | 1 | 13 | 8% | 1% to 33% |
| education=graduate | 2 | 17 | 18% | 6% to 41% |
| education=high_school | 0 | 29 | 7% | 2% to 22% |
| education=high_school | 1 | 30 | 17% | 7% to 34% |
| education=high_school | 2 | 27 | 4% | 1% to 18% |
| education=some_college | 0 | 20 | 10% | 3% to 30% |
| education=some_college | 1 | 26 | 15% | 6% to 34% |
| education=some_college | 2 | 28 | 7% | 2% to 23% |
| employment=full_time | 0 | 54 | 11% | 5% to 22% |
| employment=full_time | 1 | 58 | 14% | 7% to 25% |
| employment=full_time | 2 | 68 | 13% | 7% to 23% |
| employment=part_time | 0 | 13 | 8% | 1% to 33% |
| employment=part_time | 1 | 21 | 29% | 14% to 50% |
| employment=part_time | 2 | 13 | 0% | 0% to 23% |
| employment=retired | 0 | 10 | 10% | 2% to 40% |
| employment=retired | 1 | 10 | 10% | 2% to 40% |
| employment=self_employed | 2 | 12 | 8% | 1% to 35% |
| gender=man | 0 | 37 | 11% | 4% to 25% |
| gender=man | 1 | 44 | 11% | 5% to 24% |
| gender=man | 2 | 60 | 10% | 5% to 20% |
| gender=woman | 0 | 55 | 7% | 3% to 17% |
| gender=woman | 1 | 56 | 20% | 11% to 32% |
| gender=woman | 2 | 46 | 13% | 6% to 26% |
| household=couple | 0 | 30 | 7% | 2% to 21% |
| household=couple | 1 | 28 | 18% | 8% to 36% |
| household=couple | 2 | 23 | 13% | 5% to 32% |
| household=family_with_children | 0 | 30 | 10% | 3% to 26% |
| household=family_with_children | 1 | 33 | 24% | 13% to 41% |
| household=family_with_children | 2 | 40 | 12% | 5% to 26% |
| household=lives_alone | 0 | 12 | 17% | 5% to 45% |
| household=lives_alone | 1 | 22 | 5% | 1% to 22% |
| household=lives_alone | 2 | 20 | 5% | 1% to 24% |
| household=multigenerational | 1 | 12 | 17% | 5% to 45% |
| household=multigenerational | 2 | 10 | 20% | 6% to 51% |
| household=shared_housing | 0 | 12 | 0% | 0% to 24% |
| household=shared_housing | 2 | 13 | 8% | 1% to 33% |
| income_band=high | 1 | 10 | 40% | 17% to 69% |
| income_band=high | 2 | 11 | 36% | 15% to 65% |
| income_band=low | 0 | 21 | 0% | 0% to 15% |
| income_band=low | 1 | 24 | 0% | 0% to 14% |
| income_band=low | 2 | 28 | 0% | 0% to 12% |
| income_band=middle | 0 | 24 | 8% | 2% to 26% |
| income_band=middle | 1 | 34 | 21% | 10% to 37% |
| income_band=middle | 2 | 35 | 14% | 6% to 29% |
| income_band=upper_middle | 0 | 25 | 20% | 9% to 39% |
| income_band=upper_middle | 1 | 25 | 20% | 9% to 39% |
| income_band=upper_middle | 2 | 20 | 15% | 5% to 36% |
| income_band=very_low | 0 | 16 | 0% | 0% to 19% |
| income_band=very_low | 2 | 12 | 0% | 0% to 24% |
| price_sensitivity=high | 0 | 44 | 5% | 1% to 15% |
| price_sensitivity=high | 1 | 36 | 3% | 0% to 14% |
| price_sensitivity=high | 2 | 37 | 5% | 1% to 18% |
| price_sensitivity=low | 0 | 15 | 13% | 4% to 38% |
| price_sensitivity=low | 1 | 18 | 33% | 16% to 56% |
| price_sensitivity=low | 2 | 20 | 35% | 18% to 57% |
| price_sensitivity=moderate | 0 | 25 | 16% | 6% to 35% |
| price_sensitivity=moderate | 1 | 32 | 25% | 13% to 42% |
| price_sensitivity=moderate | 2 | 26 | 12% | 4% to 29% |
| price_sensitivity=very_high | 1 | 15 | 7% | 1% to 30% |
| price_sensitivity=very_high | 2 | 23 | 0% | 0% to 14% |
| region=midwest | 0 | 16 | 0% | 0% to 19% |
| region=midwest | 1 | 22 | 18% | 7% to 39% |
| region=midwest | 2 | 25 | 8% | 2% to 25% |
| region=northeast | 0 | 17 | 6% | 1% to 27% |
| region=northeast | 1 | 16 | 6% | 1% to 28% |
| region=northeast | 2 | 18 | 17% | 6% to 39% |
| region=south | 0 | 37 | 8% | 3% to 21% |
| region=south | 1 | 42 | 19% | 10% to 33% |
| region=south | 2 | 35 | 6% | 2% to 19% |
| region=west | 0 | 23 | 17% | 7% to 37% |
| region=west | 1 | 21 | 14% | 5% to 35% |
| region=west | 2 | 28 | 18% | 8% to 36% |
| tech_adoption=early_adopter | 0 | 16 | 0% | 0% to 19% |
| tech_adoption=early_adopter | 1 | 14 | 7% | 1% to 31% |
| tech_adoption=early_adopter | 2 | 17 | 18% | 6% to 41% |
| tech_adoption=early_majority | 0 | 19 | 21% | 9% to 43% |
| tech_adoption=early_majority | 1 | 45 | 20% | 11% to 34% |
| tech_adoption=early_majority | 2 | 41 | 15% | 7% to 28% |
| tech_adoption=innovator | 2 | 10 | 20% | 6% to 51% |
| tech_adoption=laggard | 0 | 22 | 5% | 1% to 22% |
| tech_adoption=laggard | 1 | 13 | 0% | 0% to 23% |
| tech_adoption=laggard | 2 | 14 | 0% | 0% to 22% |
| tech_adoption=late_majority | 0 | 27 | 7% | 2% to 23% |
| tech_adoption=late_majority | 1 | 22 | 23% | 10% to 43% |
| tech_adoption=late_majority | 2 | 24 | 4% | 1% to 20% |

_Segments with fewer than 10 valid responses are hidden._

## Top objections

- price: 253 (84%)
- complexity: 17 (6%)
- already have alternative: 8 (3%)

## Representative responses

- "I can't afford a fancy mug that costs more than a decent dinner out." (objection: price; source trial #101, persona P4-00002)
- "I'm a tight budget and this mug is way overpriced for what it does." (objection: price; source trial #102, persona P4-00004)
- "I'm not tech-savvy and I prefer simple, familiar products, so this smart mug with all the tech seems too complicated for me." (objection: complexity; source trial #134, persona P4-00032)
- "I'm not tech-savvy and I doubt this smart mug would be worth the extra cost for simple coffee or tea." (objection: complexity; source trial #138, persona P4-00038)
- "I already have a trusty old mug that keeps my drinks warm without needing any fancy technology." (objection: already have alternative; source trial #112, persona P4-00014)
- "I've got a decent kettle, can't imagine needing a smart mug." (objection: already have alternative; source trial #249, persona P4-00150)
- "I'm a tight budget and this mug is way overpriced for what it does." (benefit: saves money; source trial #102, persona P4-00004)
- "I can barely afford tuition and living expenses, this mug would be a luxury item." (benefit: saves money; source trial #105, persona P4-00006)
- "I can't afford a fancy mug that costs more than a decent dinner out." (benefit: saves time; source trial #101, persona P4-00002)
- "I've already got a good coffee maker, and the mug is just a waste of money." (benefit: saves time; source trial #103, persona P4-00001)
- "I don't mind the convenience of a self-heating mug, but $129 is a lot for something that seems like it should be more affordable." (benefit: convenience; source trial #110, persona P4-00010)
- "I can't justify spending so much on a mug when there are cheaper alternatives that serve my needs." (benefit: convenience; source trial #116, persona P4-00017)

## Contradictory patterns

- income_band=high differs from the overall top-2-box share by +24 points (n=10)
- income_band=high differs from the overall top-2-box share by +25 points (n=11)
- price_sensitivity=low differs from the overall top-2-box share by +24 points (n=20)

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
    "id": 2,
    "name": "WarmMug pricing test",
    "kind": "pricing",
    "research_question": "How does the price of a self-heating smart mug change simulated purchase interest?",
    "hypothesis": "Interest should fall as price rises; a $129 price should be clearly less attractive than $49.",
    "scenario": {
      "product_name": "WarmMug",
      "description": "A self-heating smart mug that keeps coffee or tea at your chosen temperature for up to 6 hours, with a charging coaster and a phone app.",
      "price_usd": null,
      "category": "kitchen gadgets",
      "headline": null
    },
    "config": {
      "design": "between",
      "repeats": 1,
      "seed": 3
    },
    "treatments": [
      {
        "idx": 0,
        "label": "$49",
        "params": {
          "price_usd": 49.0
        }
      },
      {
        "idx": 1,
        "label": "$79",
        "params": {
          "price_usd": 79.0
        }
      },
      {
        "idx": 2,
        "label": "$129",
        "params": {
          "price_usd": 129.0
        }
      }
    ]
  },
  "population": {
    "version_id": 4,
    "version": 1,
    "size": 300,
    "seed": 21,
    "source": "generated",
    "spec_sha256_16": "6bff903f6afc66db"
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
    "seed": 3
  },
  "prompt": {
    "version": "concept-v1",
    "sha256_12": "33cb8835fdc8"
  },
  "trials_planned": 300,
  "hardware": {
    "captured_at": "2026-11-03T00:57:32.090666Z",
    "os": "Darwin",
    "os_version": "26.5.2",
    "arch": "arm64",
    "chip": "Apple M4",
    "apple_silicon": true,
    "cpu_cores_total": 10,
    "cpu_cores_performance": 4,
    "ram_total_mb": 16384,
    "ram_available_mb": 3646,
    "swap_used_mb": 7394,
    "disk_free_mb": 12560,
    "disk_total_mb": 233752,
    "metal": "Metal 4",
    "on_battery": false,
    "low_power_mode": false,
    "sleep_prevented": true,
    "notes": []
  }
}
```
