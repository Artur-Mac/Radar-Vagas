# Project Review after Época 3

Review date: 2026-07-26

## Evidence-based status

Épocas 1–3 now provide a reproducible Python project, typed configuration, public-source
catalogs, four tested connectors, retry policy, isolated multi-source execution, raw run
storage, exact in-run deduplication, quarantine, manifests, and CLI commands.

The validated live run `run_20260726_215733_2d39376f` collected 300 records:

| Source | Fetched | Valid | Regex-relevant |
| --- | ---: | ---: | ---: |
| Remotive | 37 | 37 | 30 |
| Arbeitnow | 100 | 100 | 39 |
| Greenhouse Canonical | 100 | 100 | 99 |
| Greenhouse GitLab | 63 | 63 | 63 |

The volume criterion passed for raw valid records. The relevance count is not a quality result:
searching entire payloads for broad words such as `data` and `AI` strongly over-classifies
general technical roles and company boilerplate.

## Strengths

- Raw payloads are retained before future normalization or enrichment.
- Source errors are represented separately from healthy empty results.
- HTTP retries and waits are testable without real delays.
- Unit and integration-style tests are offline.
- Local artifacts and environment files are excluded from Git.
- PoC claims remain explicitly separated from validated production behavior.

## Technical debt before Época 4

1. Raw validation trusts connector-provided hashes and does not require parseable JSON.
2. Exact duplicate detection is limited to one execution; there is no stable cross-run identity.
3. Rejected payload metadata exists mainly in the manifest, not in a self-contained quarantine
   envelope.
4. Global-limit scheduling favors catalog order and may prevent later sources from running.
5. The aggregate run has no explicit success/partial/failure state.
6. The CLI contains dependency construction and output rendering that should move to application
   services.
7. Catalog metadata does not yet record terms, authentication, redistribution, or documented
   rate limits.
8. The project has no CI workflow, type-checking gate, migration strategy, or coverage policy.

## Improvements not explicit in the original epic map

- Define data retention and deletion controls for raw descriptions.
- Add provenance for every derived field, including rule or prompt version.
- Introduce deterministic fixture replay as a first-class command.
- Add contract tests for source schema drift and saved HTTP responses.
- Use fair source scheduling so a large early source cannot consume the global limit.
- Add observability cardinality rules to keep source/job identifiers out of metric labels.
- Record licenses and redistribution constraints per source before publishing datasets.
- Add backup/restore verification for the local database once historical storage is introduced.
