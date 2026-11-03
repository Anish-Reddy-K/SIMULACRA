# Performance and scaling (Apple M4, 16 GB, macOS 26.5)

Every number here was measured on this machine. Workload: product-concept trials (one persona, one structured JSON decision per call), Qwen2.5 3B Instruct Q4_K_M served by llama.cpp b11960 (`llama-server`), personas with template biographies unless stated. Raw data: `docs/performance/` and the app's run history.

## What was optimized and what it bought (80-trial runs, same 80 personas)
The first number in each row is the starting point of that comparison. Repeats of an identical configuration varied by about 4 percent, so differences below that are noise.

| Change | Valid trials/min | Completion tokens per trial | Note |
|---|---|---|---|
| Baseline: 4 slots, original prompt, batch 10 | 58.2 | 69 | warm-up run: 56.1 |
| Shorter requested reason (prompt v2) | 69.0 | 54 | +19 percent; generated tokens dominate cost |
| Persona card budget 300 to 150 tokens | 75.3 | 54 | prompt tokens unchanged (306); the card was already short, so this is noise, not a gain |
| 6 server slots (concurrency 6) | 80.9 | 54 | |
| 8 server slots (concurrency 8) | 85.2 and 88.1 | 54 | |
| 12 server slots (concurrency 12) | 105.3 | 54 | |
| 16 server slots (concurrency 16) | 102.6 | 54 | no further gain over 12 |
| 12 slots, batch size 10 | 104.7 | 54 | batch size caps in-flight requests per worker |
| 12 slots, batch size 24 | **115.2** | 54 | two waves of 12 per batch; chosen |
| 12 slots, batch size 40 / 80 | 104.9 / 111.0 | 54 | within noise of 24; larger batches slow pause and crash recovery |

Chosen configuration: prompt v2, 12 slots, concurrency 12, batch size 24. The mock-free test suite is unaffected because v1 remains the default prompt variant; v2 is selected per run and recorded in the manifest and report.

What did not help (or was not tested): persona card shrinking for short biographies; slot counts above 12; running other model servers concurrently (not done; it would hurt). Prefix caching is on in llama-server by default and the offer text is placed first in every prompt, but its separate effect was not isolated.

## Scale runs
