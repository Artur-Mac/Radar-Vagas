# Data Career Radar (Radar-Vagas)

**Data Career Radar** is a local-first job market intelligence platform focused on Data Engineering, Data Science, Machine Learning, Analytics Engineering, MLOps, and AI Engineering roles.

---

## 1. Project Goal & Current Status (Época 4 closure candidate)

Épocas 1 and 2 established the local foundation and connector framework. Época 3 added
multi-source ingestion, run manifests, raw payload persistence, exact in-run deduplication,
quarantine, pagination, and deterministic relevance screening.

Época 4 now has a broad closure candidate: DuckDB history, SHA-256 Content-Addressed
Storage (CAS), versioned text cleaning, a persisted normalization-link boundary, quarantine,
backup/restore, retention preview and pruning, migration checksums, source governance, and
scale tests. Formal closure still requires operational validation of concurrent backup behavior
and an end-to-end normalized record in Época 5.

**Completed Features:**
- **Core Package**: Typed configuration, CLI, formatted logging, and Ollama diagnostics.
- **Source Catalog**: TOML-driven source configurations (`catalogs/`) with governance metadata (`access_type`, `authentication_required`, `terms_url`).
- **Connector Framework**: Protocol-based interface with 4 production connectors (Remotive, Arbeitnow, Greenhouse, Lever).
- **HTTP Policy**: Centralized timeouts, retries with exponential backoff, rate limiting, and custom user-agents.
- **Fair Ingestion Scheduling**: Dynamic round-robin rotation via a configurable `scheduling_quantum`.
- **Local Ingestion Storage**: Atomic raw run persistence under `data/runs/<run_id>/`.
- **Historical Database & CAS**: Idempotent DuckDB metadata storage linked to SHA-256 CAS payload blobs with integrity verification.
- **Versioned Cleaned Text**: Deterministic HTML tag stripping, entity decoding, and transformation versioning stored in `cleaned_source_text`.
- **Quarantine**: Failed raw records are captured in `historical_quarantine`; failed runs remain
  retryable by correcting their original files and rerunning `history import`.
- **Backup & Restore**: Backups are atomically published after copying the checkpointed DB,
  blobs, and manifest. Do not run a backup concurrently with a historical writer.
- **Retention Controls**: Configurable age and run-count pruning defaults to a dry-run preview
  and requires `--force` for deletion.
- **Migration Hardening**: Migration identity and SHA-256 checksum tracking in `schema_migrations` to prevent migration tampering.

> [!NOTE]
> **PoC Technical Review Note**: The initial PoC proved end-to-end data flow (ingestion, raw storage, canonical schema mapping, DuckDB analytics). Per [TECHNICAL_REVIEW.md](poc/TECHNICAL_REVIEW.md), local LLM quality, fuzzy deduplication, and recommendations remain explicitly planned for future epochs (Épocas 5–8).

---

## 2. Requirements

- **Linux OS**
- **Python**: $\ge 3.12.3$
- **uv**: Python package and environment manager
- **Ollama** (Optional): Local LLM inference server (Installed model on local host: `gemma4:26b`)

---

## 3. Installation & Environment Setup

1. **Clone & Set Up Environment**:
   ```bash
   uv sync --extra dev --frozen
   ```

2. **Configure Environment Variables**:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

   Key configuration variables in `.env`:
   - `ENVIRONMENT`: `development` | `testing` | `production`
   - `LOG_LEVEL`: `INFO` | `DEBUG`
   - `DB_PATH`: `data/radar_vagas.db`
   - `OLLAMA_BASE_URL`: `http://localhost:11434`
   - `OLLAMA_MODEL`: `gemma4:26b` (or `llama3.2`)

---

## 4. Execution & Diagnostics

### Application CLI Commands
You can run the application using `radar-vagas` or `uv run radar-vagas`:

- **Display Application Configuration**:
  ```bash
  uv run radar-vagas info
  ```

- **Run Environment & Ollama Diagnostic Check**:
  ```bash
  uv run radar-vagas doctor
  ```

- **List Registered Data Sources**:
  ```bash
  uv run radar-vagas sources --active-only
  ```

- **Collect a bounded sample**:
  ```bash
  uv run radar-vagas collect --limit 50 --per-source-limit 25 --scheduling-quantum 10
  ```

- **Inspect a persisted run**:
  ```bash
  uv run radar-vagas runs show <run-id>
  ```

- **Manage Historical Storage (Import, Stats, Verify, Replay, Clean, Backup, Restore, Prune)**:
  ```bash
  # Initialize and import local runs into DuckDB + CAS
  uv run radar-vagas history init --db-path data/radar_vagas.db
  uv run radar-vagas history import --output-dir data --db-path data/radar_vagas.db
  uv run radar-vagas history stats --db-path data/radar_vagas.db
  uv run radar-vagas history verify --db-path data/radar_vagas.db
  uv run radar-vagas history replay <run-id> --db-path data/radar_vagas.db --limit 10 --jsonl

  # Clean HTML source text into plain text
  uv run radar-vagas history clean --db-path data/radar_vagas.db

  # Publish a local snapshot (do not run concurrently with a history writer)
  uv run radar-vagas history backup --dest-dir backups/snapshot_1 --db-path data/radar_vagas.db

  # Restore historical storage from a backup
  uv run radar-vagas history restore --backup-dir backups/snapshot_1 --target-dir restored_data --force

  # Preview data retention pruning (dry-run)
  uv run radar-vagas history prune --max-age-days 30 --keep-min-runs 5

  # Execute retention pruning
  uv run radar-vagas history prune --max-age-days 30 --keep-min-runs 5 --force

  # Inspect records in historical quarantine
  uv run radar-vagas history quarantine --db-path data/radar_vagas.db
  ```

---

## 5. Developer Quality Tools (Test, Lint, Format)

All development commands are accessible via `make` shortcuts:

- **Run Automated Test Suite**:
  ```bash
  make test
  # or: uv run pytest
  ```
  *(Note: Unit tests run 100% offline without network or Ollama dependencies)*

- **Run Linter (Ruff)**:
  ```bash
  make lint
  # or: uv run ruff check .
  ```

- **Run Code Formatter**:
  ```bash
  make format
  # or: uv run ruff format .
  ```

---

## 6. Directory Structure

```text
Radar-Vagas/
├── pyproject.toml              # Dependencies, build configs, CLI script entrypoint
├── Makefile                    # Developer shortcut commands
├── README.md                   # System documentation and setup guide
├── .env.example                # Environment configuration template
├── .github/workflows/ci.yml    # GitHub Actions CI workflow
├── catalogs/                   # TOML source catalog files with governance metadata
│   ├── aggregators.toml        # Remotive, Arbeitnow
│   ├── greenhouse.toml         # Greenhouse ATS boards
│   └── lever.toml              # Lever ATS companies
├── docs/                       # Project specifications & reports
│   ├── AGENTS.md
│   ├── Epochs.md
│   ├── POC.md
│   ├── ARCHITECTURE.md
│   └── EPOCH4_REPORT.md
├── src/
│   └── radar_vagas/
│       ├── __init__.py         # Package version
│       ├── cli.py              # Application CLI Entrypoint
│       ├── core/               # Configuration, Logging, Ingestion & Services
│       │   ├── cleaner.py      # TextCleaner service for deterministic HTML stripping
│       │   ├── history_service.py # Historical operations & backup/restore orchestration
│       │   └── ingestion.py    # ConnectorRunner with scheduling quantum
│       ├── domain/             # Domain Models & Connector Protocols
│       │   ├── models.py       # RawJobRecord, CleanedSourceText, BackupManifest, etc.
│       │   └── connector.py    # JobConnector Protocol
│       ├── connectors/         # Production connector implementations
│       └── infrastructure/     # DuckDB Storage & HTTP Policies
│           ├── history.py      # HistoricalStorage (DuckDB + CAS + Migrations + Backup)
│           └── http.py         # HttpPolicy, polite_get, retry/backoff
└── tests/                      # 100% offline test suite
```
