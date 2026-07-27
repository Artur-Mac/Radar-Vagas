# Época 4 Closure Report: Raw Data and Historical Storage

**Original validation:** 2026-07-26
**Closure audit:** 2026-07-27
**Status:** COMPLETE

## 1. Executive Summary

Época 4 delivers an offline-tested historical storage layer based on DuckDB and SHA-256
Content-Addressed Storage (CAS). It preserves raw observations, tracks source-job state over
time, derives versioned cleaned text, supports replay, records quarantine failures, and
provides retention and verified backup/restore operations.

The only remaining closure risk in the original report was concurrent mutation during a
backup. That risk is now resolved by a shared inter-process history lock, exercised by real
multiprocessing tests and by the complete Época 5 normalization flow.

## 2. Acceptance Criteria and Evidence

| Acceptance criterion | Evidence | Status |
| :--- | :--- | :--- |
| Original payloads remain accessible | CAS reads validate the SHA-256 address; integrity checks detect missing, corrupt, orphaned, and incorrectly placed files. | Passed |
| Existing jobs are updated instead of blindly duplicated | `(source_name, source_job_id)` is stable in `source_jobs`; observations remain append-only and imports are idempotent by run ID. | Passed |
| Changed descriptions create a snapshot or version | `changed_since_previous` tracks raw changes; cleaned artifacts are versioned; distinct observations receive distinct deterministic normalized IDs. | Passed |
| Disappeared jobs can be identified | Complete source runs advance `missing_complete_runs`; partial runs do not falsely close jobs. | Passed |
| Raw records are linked to normalized records | `normalized_job_links` validates source identity, raw hash, observation, and optional cleaned artifact ownership. | Passed end to end |
| Backup cannot race with a writer | All history mutators and the entire checkpoint/CAS-copy interval use the same stable sibling lock file. | Passed |

## 3. Operational Controls

### Inter-process coordination

- A stable lock file sits beside the data directory, so it remains valid while restore swaps
  directories.
- Import, raw/CAS writes, cleaning, quarantine, normalization, retention, migrations, backup,
  and restore coordinate through the same lock.
- Lock contention produces an actionable CLI error instead of a low-level traceback.
- Multiprocessing tests prove that a real writer cannot interleave with a backup.

### Replay, cleaning, and quarantine

- `history replay` reconstructs persisted records without a network request.
- `history clean` produces deterministic, versioned derived text and selects the latest
  cleaned artifact deterministically.
- `history quarantine` exposes failed records. Repairing the source run and importing it
  again is the supported retry path.

### Backup, restore, retention, and migrations

- Backup and restore use staging directories, checksum validation, and complete integrity
  verification before publication.
- Restore protects the target with the stable lock and keeps the old target until its
  replacement is ready.
- Retention defaults to preview, preserves a configured minimum number of runs, and deletes
  normalized provenance, normalized records, links, cleaned data, observations, and CAS
  metadata in retry-safe dependency order.
- Migration checksums detect changed or unknown migration histories.

## 4. Real-Data Evidence

The closure audit reused a 2,097-record run without new network collection:

- all 2,097 raw observations and blobs were imported and cleaned;
- all 2,097 observations were normalized and linked to their raw and cleaned inputs;
- a repeated normalization of the same version skipped all 2,097 records;
- a backup and restore preserved the observations, blobs, normalized records, links, and
  field-level provenance exactly;
- restored integrity reported no missing, corrupt, orphaned, or incorrectly placed blobs.

Timings are local execution evidence, not portable performance guarantees. Import and
cleaning took approximately 26 and 24 seconds respectively on the audit machine.

## 5. Conclusion

The historical foundation is closed. Época 5 may rely on coordinated mutation,
content-addressed raw preservation, versioned derived data, and verified recovery without
requiring the former “stop every writer before backup” operational rule.
