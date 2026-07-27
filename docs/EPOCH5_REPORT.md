# Época 5 Completion Report: Job Normalization

**Date:** 2026-07-27
**Status:** COMPLETE

## 1. Executive Summary

Época 5 delivers a deterministic, versioned normalization engine for Data Career Radar. It
maps Greenhouse, Lever, Remotive, and Arbeitnow observations to one canonical job schema,
while retaining the raw payload, the cleaned input, the exact source identity, and
field-level provenance.

The completion audit went beyond fixture tests and normalized a real 2,097-record historical
run. It exposed and resolved scale, identity, concurrency, retention, and false-positive
issues before closure.

## 2. Acceptance Criteria

| Acceptance criterion | Evidence | Status |
| :--- | :--- | :--- |
| Supported sources share one canonical schema | Typed `CanonicalJobPost` plus source adapters for Greenhouse, Lever, Remotive, and Arbeitnow. | Passed |
| Original values and provenance remain available | Canonical records link to observation, raw hash, optional cleaned artifact, and deterministic field provenance. | Passed |
| Missing values are consistent | Missing or ambiguous fields remain `None`; URLs and enums are validated conservatively. | Passed |
| Rules are versioned and testable | TOML taxonomies, rule version metadata, golden fixtures, adapter tests, and boundary tests. | Passed |
| Invalid records are not silently accepted | Read, parse, adapter, and ownership failures are counted and quarantined. | Passed |
| Reprocessing is safe | Identity is deterministic per observation and rule version; same-version runs skip, new versions append. | Passed |
| Operations are safe under concurrency | Normalization holds the shared history lock across discovery, transformation, and persistence. | Passed |

## 3. Important Audit Corrections

- Normalized IDs include the observation identity, so changed snapshots cannot collide.
- Greenhouse and Lever use the exact catalog connector identity (`board + id` or
  `company + id`) rather than the provider's bare ID.
- Storage rejects mismatched source identities, raw hashes, cleaned artifacts, and
  provenance ownership.
- The latest cleaned artifact is selected deterministically when more than one cleaner
  version exists.
- `--limit` applies to pending work rather than repeatedly selecting already processed rows.
- Persistence uses validated, bounded transaction chunks. This removed a native DuckDB crash
  found only during the 2,097-record run and leaves committed chunks safely restartable.
- Retention includes normalized provenance, records, and links in foreign-key-safe order.
- Taxonomy matches use token boundaries, avoiding cases such as `DE` inside `remote`,
  `staff` inside `staffing`, or `lead` inside `leadership`.
- Unsupported or deceptively similar source names fail clearly instead of receiving an
  arbitrary adapter.

## 4. Real-Data Validation

The final code path produced the following result on an existing run:

- observations discovered: **2,097**;
- records normalized: **2,097**;
- rejected/quarantined: **0 / 0**;
- sources represented: **9**;
- normalization time: **41.341 seconds**;
- same-version re-run: **0 written, 2,097 skipped in 0.052 seconds**.

The audit also retained multiple rule histories and verified a final snapshot containing
6,341 normalized records and links, 62,104 provenance rows, and 2,097 CAS blobs. Restore
reproduced those counts exactly and passed the full integrity check.

The final offline quality gate passed Ruff linting, Ruff formatting verification, Git diff
validation, and all **142 tests** in **116.72 seconds**.

## 5. Honest Quality Findings

The full source corpus is intentionally broader than data careers. Under the conservative
final taxonomy, 2,025 of 2,097 postings had no data-career role family. This is not a reason
to make normalization more aggressive: doing so would turn unrelated jobs into false data
roles.

It is a product signal for Época 6. Before optional model inference, the system needs a
deterministic enrichment-eligibility gate that separates:

- clearly relevant data/AI jobs;
- clearly irrelevant jobs that must consume no inference;
- ambiguous candidates that may benefit from bounded provider evaluation.

Location, work arrangement, employment type, and seniority also remain absent when the
source does not provide trustworthy evidence. Época 6 should enrich unresolved facts only
when it can store supporting evidence; it must not overwrite reliable Época 5 values.

## 6. Scope Boundaries

- No LLM is required or used for Época 5 normalization.
- Cross-source duplicate detection remains Época 7.
- The eight-posting golden fixture is a regression foundation, not a statistically complete
  quality evaluation. Época 6 requires at least 30 manually reviewed postings and
  field-level metrics.
- Import, cleaning, and normalization are fast enough for the current private workflow, but
  their per-row storage path should be profiled before a hosted, high-volume deployment.

## 7. Next Milestone

Proceed to Época 6: Evidence-Based Hybrid Enrichment, following
`docs/PRODUCT_DIRECTION.md`. The no-LLM experience must remain useful, optional inference
must be provider-independent and bounded, and all extracted facts must be evidence-backed,
versioned, cached, and reusable by a future web product.
