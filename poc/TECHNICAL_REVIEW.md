# PoC Technical Review

Review date: 2026-07-26

## Outcome

The PoC proves that public connectors, raw persistence, canonical normalization, and local
analytics can run end to end. It does not yet validate the product's three decisive claims:
local LLM quality/performance, deduplication quality, or recommendation usefulness.

The latest run collected 337 records and normalized all of them. After deduplication, only 11
of 301 unique postings passed a high-precision Data/AI title gate. Ollama was unavailable, so
all enrichment came from the deterministic fallback and cannot be used as evidence for H4 or
H5.

## High-impact experiment

A relevance gate was added before enrichment and ranking. In the original report, three of the
top five recommendations were unrelated roles (content review, sales, and marketing). After
the gate, all top five titles were in-scope technical roles. The latest run also avoided 290
unnecessary enrichment attempts.

Skill detection now uses word boundaries, preventing `git` from being extracted from words
such as `digital`. Exact normalized skill matching also replaces substring matching.

Greenhouse boards and Lever companies are now sampled in round-robin order. Previously, the
first board/company could consume the entire 100-record limit, making the sample look broader
than it was.

## Prioritized next work

### P0 — required before a go/no-go decision

1. Create a labeled evaluation fixture with at least 100 postings, including hard negatives.
   Label relevance, role family, seniority, required/preferred skills, and duplicate groups.
2. Run Ollama with the intended model and hardware. Record model identity, prompt version,
   validation failures, retries, latency percentiles, and throughput for an unattended
   100-record batch.
3. Manually label the top 10 recommendations and require at least 8 relevant results, matching
   the PoC acceptance criterion.
4. Expand targeted source coverage or pagination. Eleven relevant jobs is far below the
   200-job H1 target, and a fixed 100-record general sample is not an adequate volume test.

### P1 — reliability and evaluation quality

1. Return structured connector diagnostics for HTTP errors, non-200 responses, pagination,
   rate limits, and empty results. An empty list currently conflates a healthy empty source
   with a failed source.
2. Store immutable run snapshots with a run ID and a manifest. The flat raw/normalized
   directories retain files from earlier executions, so directory counts are not current-run
   counts.
3. Strip HTML before measuring description richness or sending text to the model.
4. Add labeled precision/recall evaluation for deduplication. The current implementation has
   exact hashes and exact title/company/location signatures, but no fuzzy text similarity.
5. Stratify the enrichment sample across sources and role families instead of taking the
   first N relevant records.

### P2 — ranking and product value

1. Move the candidate profile and weights out of source code into versioned configuration.
2. Treat required and preferred skills differently. Do not award a neutral 50% skill score
   when no skills were extracted; represent insufficient evidence explicitly.
3. Add eligibility constraints for geography, language, seniority, and employment type before
   computing a preference score.
4. Validate actionable insights on the full relevant corpus. Current counts are exploratory
   and based on heuristic enrichment.

## Verification

- `pytest`: 6 tests passed.
- `ruff`: all project checks passed.
- End-to-end pipeline: completed with 337 collected, 337 normalized, 301 unique, 11 relevant,
  and 290 excluded before enrichment.
