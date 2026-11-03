# A/B tests, ad comparisons and pricing

## Designs
- **Between subjects (default)**: every persona is randomly assigned to exactly one treatment by a seeded hash of (seed, persona). All treatments are drawn from the same population, so baselines are identical in distribution. Isolation is structural: a trial prompt contains only its own treatment's text (verified in tests at the prompt level and against stored trial prompts of a real run).
- **Within subjects**: every persona sees every treatment as separate, independent calls, analyzed as matched pairs.
- **Templates**: product concept, ad comparison (2-12 headlines), pricing (2-12 distinct prices), plus cloning an experiment's exact design.

## Statistics (`analysis/stats.py`, `analysis/compare.py`)
For each treatment versus the baseline (treatment 0): top-2-box difference with a Newcombe (method 10) interval, two-sided Fisher exact test, Cohen's h, relative lift, Welch's t-test and Cohen's d for mean appeal. Within-subjects runs use the exact McNemar test and a paired t-test. Pairwise p-values are Holm-adjusted. Segment comparisons are exploratory, need at least 10 valid responses in both arms, and are Holm-adjusted across every segment tested. Randomization is checked with a chi-square test per attribute (Holm-adjusted). Pricing runs add a simulated interest-by-price curve and flag statistically detectable increases in interest at a higher price as implausible patterns (model artifacts). With repeats above 1, tests use only each persona's first repeat so observations are independent; extra repeats are reported as run-to-run stability.

## Verification performed
- Newcombe interval reproduces Newcombe (1998) example 1 (56/70 vs 48/80: 0.0524 to 0.3339).
- Holm adjustment matches a hand-worked example; Cohen's h matches the closed form.
- Fisher exact p-values match an independent hypergeometric implementation and SciPy; McNemar matches the binomial tail; Welch matches the manual t and Welch-Satterthwaite computation; chi-square matches a manual calculation.
- Null simulations (2,000 A/A experiments): unadjusted false-positive rate below 6 percent, Holm-adjusted family-wise rate below 6 percent; power above 80 percent for a 40 vs 25 percent difference at n=200 per arm. Random assignment flagged imbalance in fewer than 12 percent of 150 seeds (nominal 5 percent).
- Every statistic in a comparison is recomputed independently in tests from stored trial rows.

## Real run (this machine)
300 personas (template biographies), three prices, between subjects, llama.cpp b11960, Qwen2.5 3B Q4_K_M, concurrency 4: 300 of 300 valid trials, 360 s wall time (about 50 valid trials/min). Arm sizes 93, 101, 106 (randomization balance check: smallest Holm-adjusted p = 0.49).

| Price | n | Top-2-box |
|---|---|---|
| $49 | 93 | 8.6% |
| $79 | 101 | 15.8% |
| $129 | 106 | 11.3% |

No difference was statistically detectable (Holm-adjusted p = 0.27 for $79 vs $49 and 0.64 for $129 vs $49), and the simulated curve is not monotone. The honest reading: at this sample size this small model's stated purchase interest does not show a detectable price effect. That says nothing about how real shoppers respond to price. The report is `docs/examples/warmmug-pricing-test.md`.

## Limitations
- Statistical significance describes the model's behavior in this simulation only.
- 100 personas per arm only detects large effects; use more personas or repeats to measure variation.
- Segment findings are exploratory even after adjustment.
