# Epic 3: Initial Job Ingestion - Summary

## Objectives Achieved
1. **Domain Models**: Defined `RunState`, `Pagination`, `RejectedRecord`, `QuarantinedRecord`, `ExactDuplicate`, `SourceRunSummary`, `IngestionSummary`, and `RunManifest` in `models.py`.
2. **HTTP Policy Enhancements**: Updated `polite_get` to accept `sleep_fn` (for mockable delays) and respect `Retry-After` headers on 429 status codes. Also implemented explicit exception trapping and retry limits for `TimeoutException` and `ConnectError`, alongside safe logging.
3. **Connector Pagination**: All 4 connectors (`Remotive`, `Arbeitnow`, `Greenhouse`, `Lever`) were updated to support the new `cursor: Pagination | None` argument in `fetch()`. Arbeitnow dynamically follows its `next` links, while the others correctly report single-page termination (`has_more=False`).
4. **Ingestion Pipeline (`ConnectorRunner`)**: Implemented the core ingestion runner that orchestrates connector execution, captures metrics/errors without crashing the whole run (Source Isolation), applies deterministic Data/AI relevance filtering (Regex), and handles exact deduplication per run.
5. **Local Persistence (`LocalStorage`)**: Configured local JSON file storage inside `data/runs/<run_id>/` that persists raw valid payloads, rejected payloads in quarantine, and the final run manifest. Writes are atomic and refuse silent overwrite.
6. **CLI Integration**: Extended `radar-vagas` with `collect` (executes ingestion with limits, dry run, filters) and `runs show <run_id>` (displays a run manifest).
7. **Comprehensive Testing**: Created integrated tests for storage and ingestion pipelines using 100% offline mocks.

## Verification
- **Dry Run & Small Run**: Completed successfully.
- **Large Run**: `--per-source-limit 100 --limit 300` fetched 300 valid records from four
  sources. The broad regex marked 231 as potentially relevant; this is an exploratory signal,
  not a validated count of Data/AI vacancies.
- **Test Suite**: 75 tests pass offline, covering parsing, registry, connectors, HTTP policy,
  the pipeline runner, storage persistence, dry-run behavior, and validation logic.
- **Data Privacy**: The `.gitignore` was updated to safely exclude all local runs.

## Remaining before historical storage

- Validate payload JSON and recompute content hashes instead of trusting connector output.
- Replace broad text relevance with a versioned, title-first classifier and labeled evaluation.
- Add explicit aggregate run outcome and record why sources were skipped by a global limit.
- Remove remaining CLI orchestration and presentation concerns from `cli.py`.
