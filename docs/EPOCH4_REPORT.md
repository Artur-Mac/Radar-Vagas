# Época 4 Validation Report: Raw Data and Historical Storage

**Date**: 2026-07-26  
**Status**: CLOSURE CANDIDATE

## 1. Executive Summary

Época 4 has a functional, offline-tested historical storage layer based on DuckDB and
SHA-256 Content-Addressed Storage (CAS). The implementation preserves raw observations,
tracks source-job state over time, derives versioned cleaned text, supports replay, records
quarantine failures, and provides retention and backup/restore operations.

The audit corrected several gaps in the initial completion claim:

- normalization provenance is now persisted in `normalized_job_links`, not only represented
  by a Pydantic model;
- a new cleaner version produces a new derived artifact instead of being skipped;
- quarantine rows store a content hash, and the misleading placeholder “reprocess” command
  was replaced with an inspection command and an honest retry procedure;
- backup publication and restore replacement use staging directories;
- retention deletes related database rows in retry-safe dependency phases and removes CAS
  files only after the metadata commit;
- migration checksums are backfilled during the same upgrade that introduces the checksum
  column;
- documentation no longer reports synthetic performance numbers as measured evidence.

Formal closure should be recorded after the operational limitation in Section 4 is resolved
or explicitly accepted.

## 2. Acceptance Criteria and Evidence

| Acceptance criterion | Current evidence | Status |
| :--- | :--- | :--- |
| Original payloads remain accessible | CAS writes and reads validate the SHA-256 address; integrity checks detect missing, corrupt, orphaned, and incorrectly placed files. | Passed |
| Existing jobs are updated instead of blindly duplicated | `(source_name, source_job_id)` is stable in `source_jobs`; observations remain append-only and imports are idempotent by run ID. | Passed |
| Changed descriptions create a snapshot or version | `source_job_observations.changed_since_previous` tracks raw changes; cleaned artifacts are unique by observation and transformation version. | Passed |
| Disappeared jobs can be identified | Complete source runs advance `missing_complete_runs` and transition records through `possibly_inactive` and `closed`; partial runs do not. | Passed |
| Raw records are linked to normalized records | Migration 12 adds `normalized_job_links` with foreign keys to raw observations and optional cleaned artifacts. Storage round-trip tests cover the boundary. | Boundary passed; end-to-end use begins in Época 5 |

The storage API also rejects a link whose source identity, raw hash, or cleaned artifact does
not belong to the referenced observation.

## 3. Implemented Operational Controls

### Replay, cleaning, and quarantine

- `history replay` reconstructs records from persisted raw observations without a network
  request.
- `history clean` applies deterministic, versioned text transformations.
- `history quarantine` reports failed historical imports. To retry, repair the original run
  files and run `history import` again; failed runs are not marked as imported.

### Backup and restore

- A backup is assembled in a sibling staging directory and renamed to the requested
  destination only after the database, CAS tree, and manifest have been copied.
- Existing backup destinations are rejected, preventing accidental snapshot merging.
- Restore verifies the backup database checksum and complete staged storage integrity before
  replacing the target.
- Forced restore keeps the old target available until the staged replacement is ready.

### Retention and migrations

- Retention is preview-only unless `--force` is supplied.
- At least one run must be retained, and negative age values are rejected.
- Related database deletions use idempotent transactions ordered by foreign-key dependency
  (a DuckDB constraint). CAS unlink failures leave detectable orphan files rather than broken
  database references.
- Applied migrations have deterministic SHA-256 checksums; unknown future versions and
  modified applied migrations are rejected.

### Source governance and CI

- Catalog records include access type, authentication requirements, terms URLs, attribution
  requirements, redistribution notes, and review timestamps where the source policy was
  audited.
- CI installs a pinned uv action and runs the locked dependency installation, Ruff checks,
  formatting verification, Git diff checks, and the offline test suite.

### Local validation evidence

The final audit exercised an existing 2,097-record run without making another network
request. On the audit machine, import took 25.39 seconds, versioned cleaning took 23.31
seconds, snapshot publication took 0.68 seconds, and verified restore took 0.80 seconds.
The restored store contained 2,097 valid blobs and replayed all 2,097 records. These figures
are an execution record for this machine and dataset, not a portable performance guarantee.
The final offline suite passed all 124 tests in 107.52 seconds on the same machine.

## 4. Remaining Closure Risk

The snapshot is atomically *published*, but the database checkpoint and CAS copy are not
coordinated by a project-wide inter-process lock. A different process could write historical
data while a backup is being assembled. Until writer coordination is implemented and tested,
collection, import, cleaning, normalization, and retention must be stopped during
`history backup`.

Recommended closure gate:

1. introduce one inter-process history lock used by every operation that can mutate the
   database or CAS;
2. make backup acquire the same lock for the full checkpoint-and-copy interval;
3. add a multiprocessing test proving that a writer cannot interleave with a backup;
4. exercise the persisted normalization link in the first complete Época 5 record.

## 5. Conclusion

The storage foundation is suitable for beginning Época 5, provided the no-concurrent-writer
backup rule is observed. Época 5 should exercise `normalized_job_links` end to end and keep
normalization deterministic, versioned, idempotent, and fully traceable to raw data.
