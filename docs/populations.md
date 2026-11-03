# Population factory

Populations are generated structure-first: code samples demographics from an explicit spec, and a language model (optional) only writes text around the sampled facts.

## Pipeline
1. **Spec** (`populations/spec.py`): weighted categorical, ordinal and binned-numeric attributes, pairwise correlations, an optional stratification attribute, and named hard rules. Specs are plain JSON, validated on input. The bundled preset is an illustrative assumption, not census data.
2. **Sampling** (`sampler.py`): seeded NumPy. Correlated ordinal/numeric attributes use a Gaussian copula (correlated normals mapped to each attribute's marginal), and impossible correlation sets are rejected. Stratification matches a categorical attribute's shares exactly (largest-remainder allocation). Hard rules (`rules.py`) are enforced by rejection sampling with a retry budget; failures are counted, never hidden.
3. **Enrichment** (`enrich.py`, optional): the model returns bio, interests, brand attitudes and a quirk as schema-validated JSON. Deterministic contradiction checks (stated age, retired/student status, mentions of being an AI) trigger one retry and then fall back to a deterministic template bio, flagged in the persona's metadata.
4. **Diagnostics** (`diagnostics.py`): realized vs target marginals, realized vs target Spearman correlations, exact duplicate attribute sets, near-duplicate bios (3-word shingle Jaccard, sampled pairs above 200,000), lexical diversity, category coverage, rule rejections, template fallbacks.
5. **Persistence**: `populations` -> immutable `population_versions` (spec, seed, diagnostics) -> `personas`. A version is writable only while `generating`; any change creates a new version. The same spec and seed reproduce identical demographics.
6. **Context builder** (`context.py`): a compact prompt card per persona with an approximate token budget (4 characters per token; real token counts are measured by benchmarks and run telemetry).

## Import and export
JSONL export includes a header with the spec and seed. Import is strict: unknown fields are rejected, text fields are length-limited, IDs must be unique, files are limited to 20 MB, content is treated as data and never executed. CSV export prefixes cells that start with `=`, `+`, `-`, `@` to prevent spreadsheet formula injection.

## Known limitations
- Rejection sampling for hard rules shifts the marginals of the attributes involved. With the bundled preset, the realized share of "retired" is about 14 percent against a 21 percent target at 1,000 personas, and the diagnostics report this gap and explain it.
- Correlations are realized approximately (rank-coded Spearman on discretized values); realized values land a few hundredths to about 0.1 below the targets.
- Names are random neutral given names with no demographic meaning; they are not drawn from any real distribution.
- LLM bios are model-generated text. Small models produce generic, similar-sounding bios; the lexical-diversity numbers show this.
- Nothing here claims representativeness of any real population.
